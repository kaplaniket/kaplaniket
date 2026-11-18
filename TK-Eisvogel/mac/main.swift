// TK Eisvogel – Mac-Programm, Fassung 3.0 (Claude 17.11.2026). Früher „TK KI“.
// Zeigt TK Eisvogel vom eigenen Rechner (HP, nur im Tailnet). Knopf „Beenden“, ⌘Q und Fenster schließen beenden das Programm ganz.
// Bauen: siehe bauen.sh im selben Ordner.
import Cocoa
import WebKit

let NAME = "TK Eisvogel"
// Adressen des HP (Tailnet zuerst, dann Heimnetz), einmal am Mac setzen:
// defaults write de.tekin.tkki adressen "http://<Tailnet-IP>:8811,http://<Heimnetz-IP>:8811"
let ADRESSEN = (UserDefaults.standard.string(forKey: "adressen") ?? "http://tk-ki-hp.local:8811")
    .split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
let EIGENE = Set(ADRESSEN.compactMap { URL(string: $0)?.host })

class App: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate {
    var fenster: NSWindow!
    var web: WKWebView!
    var nr = 0

    func applicationDidFinishLaunching(_ n: Notification) {
        let cfg = WKWebViewConfiguration()
        cfg.userContentController.add(self, name: "tkki")       // die Oberfläche ruft darüber „beenden“
        web = WKWebView(frame: .zero, configuration: cfg)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.allowsBackForwardNavigationGestures = true
        web.setValue(false, forKey: "drawsBackground")
        fenster = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1100, height: 820),
                           styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        fenster.title = NAME
        fenster.minSize = NSSize(width: 380, height: 520)
        // Farbe des Kopfes (hell #07485a, dunkel #0b2a33) – das Fenster folgt dem Aussehen des Systems
        fenster.backgroundColor = NSColor(name: nil) { a in
            a.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? NSColor(red: 0.031, green: 0.086, blue: 0.106, alpha: 1) : NSColor(red: 0.929, green: 0.949, blue: 0.953, alpha: 1)
        }
        fenster.contentView = web
        fenster.delegate = self
        fenster.setFrameAutosaveName("TKKIFenster")
        if fenster.frame.width < 380 { fenster.center() }
        fenster.makeKeyAndOrderFront(nil)
        menue()
        laden("/")
        NSApp.activate(ignoringOtherApps: true)
    }

    func menue() {
        let haupt = NSMenu()
        let a = NSMenuItem(); haupt.addItem(a)
        let am = NSMenu()
        am.addItem(withTitle: "Über \(NAME)", action: #selector(ueber), keyEquivalent: "")
        am.addItem(NSMenuItem.separator())
        am.addItem(withTitle: "Einstellungen …", action: #selector(einstellungen), keyEquivalent: ",")
        am.addItem(NSMenuItem.separator())
        am.addItem(withTitle: "\(NAME) ausblenden", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        am.addItem(withTitle: "\(NAME) beenden", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        a.submenu = am
        let b = NSMenuItem(); haupt.addItem(b)
        let bm = NSMenu(title: "Bearbeiten")
        bm.addItem(withTitle: "Widerrufen", action: Selector(("undo:")), keyEquivalent: "z")
        bm.addItem(NSMenuItem.separator())
        bm.addItem(withTitle: "Ausschneiden", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        bm.addItem(withTitle: "Kopieren", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        bm.addItem(withTitle: "Einfügen", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        bm.addItem(withTitle: "Alles auswählen", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        b.submenu = bm
        let c = NSMenuItem(); haupt.addItem(c)
        let cm = NSMenu(title: "Darstellung")
        cm.addItem(withTitle: "Fragen", action: #selector(fragen), keyEquivalent: "1")
        cm.addItem(withTitle: "Karten", action: #selector(karten), keyEquivalent: "2")
        cm.addItem(withTitle: "iMac", action: #selector(imac), keyEquivalent: "3")
        cm.addItem(withTitle: "Gespräche", action: #selector(gespraeche), keyEquivalent: "4")
        cm.addItem(withTitle: "Mehr", action: #selector(mehr), keyEquivalent: "5")
        cm.addItem(NSMenuItem.separator())
        cm.addItem(withTitle: "Neu laden", action: #selector(neuLaden), keyEquivalent: "r")
        c.submenu = cm
        let d = NSMenuItem(); haupt.addItem(d)
        let dm = NSMenu(title: "Hilfe")
        dm.addItem(withTitle: "Impressum", action: #selector(impressum), keyEquivalent: "")
        dm.addItem(withTitle: "Datenschutz", action: #selector(datenschutz), keyEquivalent: "")
        dm.addItem(withTitle: "Urheberrecht und Lizenzen", action: #selector(lizenzen), keyEquivalent: "")
        d.submenu = dm
        NSApp.mainMenu = haupt
    }

    func laden(_ pfad: String) {
        web.load(URLRequest(url: URL(string: ADRESSEN[nr % ADRESSEN.count] + pfad)!, timeoutInterval: 20))
    }
    @objc func neuLaden() { if web.url == nil { nr = 0; laden("/") } else { web.reload() } }
    @objc func fragen() { laden("/") }
    @objc func karten() { laden("/karten") }
    @objc func imac() { laden("/imac") }
    @objc func gespraeche() { laden("/gespraeche") }
    @objc func mehr() { laden("/mehr") }
    @objc func einstellungen() { laden("/einstellungen") }
    @objc func ueber() { laden("/ueber") }
    @objc func impressum() { laden("/impressum") }
    @objc func datenschutz() { laden("/datenschutz") }
    @objc func lizenzen() { laden("/lizenzen") }

    // erste Adresse nicht erreichbar → zweite, dann verständliche Meldung
    func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) {
        let z = "\(Date()) \(ADRESSEN[nr % ADRESSEN.count]) \(e.localizedDescription)\n"
        if let h = FileHandle(forWritingAtPath: "/tmp/tkki-fehler.log") { h.seekToEndOfFile(); h.write(z.data(using: .utf8)!); h.closeFile() }
        else { try? z.write(toFile: "/tmp/tkki-fehler.log", atomically: true, encoding: .utf8) }
        nr += 1
        if nr < 4 { DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.laden("/") } }
        else {
            nr = 0
            w.loadHTMLString("<meta charset=utf-8><body style='margin:0;display:grid;place-items:center;height:100vh;background:#edf2f3;color:#0f2730;font:17px/1.5 -apple-system,system-ui'>"
                + "<div style='max-width:440px;padding:32px;text-align:center'><h2 style='margin:0 0 8px;font-size:24px'>\(NAME) ist nicht erreichbar</h2>"
                + "<p style='color:#566b73;margin:0'>Läuft der Rechner zu Hause, und ist Tailscale auf diesem Mac verbunden?<br>Mit ⌘R noch einmal versuchen.</p></div></body>", baseURL: nil)
        }
    }

    // fremde Verweise und Mail-Adressen im Standardprogramm öffnen, nicht im Fenster
    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let u = a.request.url, let s = u.scheme {
            if s == "mailto" || s == "tel" || ((s == "http" || s == "https") && a.navigationType == .linkActivated && !EIGENE.contains(u.host ?? "")) {
                NSWorkspace.shared.open(u); decisionHandler(.cancel); return
            }
        }
        decisionHandler(.allow)
    }
    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url { if EIGENE.contains(u.host ?? "") { w.load(a.request) } else { NSWorkspace.shared.open(u) } }
        return nil
    }
    // „Foto mitschicken“: Dateiauswahl
    func webView(_ w: WKWebView, runOpenPanelWith p: WKOpenPanelParameters, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let o = NSOpenPanel(); o.canChooseFiles = true; o.canChooseDirectories = false; o.allowsMultipleSelection = p.allowsMultipleSelection
        o.beginSheetModal(for: fenster) { r in completionHandler(r == .OK ? o.urls : nil) }
    }
    // Rückfragen der Oberfläche (z. B. „Routine löschen?“)
    func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "OK"); a.addButton(withTitle: "Abbrechen")
        a.beginSheetModal(for: fenster) { r in completionHandler(r == .alertFirstButtonReturn) }
    }
    func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "OK"); a.beginSheetModal(for: fenster) { _ in completionHandler() }
    }
    func userContentController(_ u: WKUserContentController, didReceive m: WKScriptMessage) {
        if "\(m.body)" == "beenden" { NSApp.terminate(nil) }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
let d = App()
app.delegate = d
app.setActivationPolicy(.regular)
app.run()
