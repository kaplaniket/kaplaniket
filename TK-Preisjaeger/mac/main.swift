// TK Preisjäger – Mac-Programm, Fassung 1.0 (Claude 26.11.2026).
// Zeigt den Preisjäger vom eigenen Rechner (HP). Angebots-Links öffnen im normalen Browser.
// Läuft auf Intel- und Apple-Chips (bauen.sh baut beide in eine Datei), ab macOS 11.
import Cocoa
import WebKit

let NAME = "TK Preisjäger"
// Adressen des HP, einmal am Mac setzen (macht einbauen.sh):
// defaults write de.tekin.preisjaeger adressen "http://<Heimnetz-IP>:8815,http://<Tailnet-IP>:8815"
let ADRESSEN = (UserDefaults.standard.string(forKey: "adressen") ?? "http://tk-ki-hp.local:8815")
    .split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
let EIGENE = Set(ADRESSEN.compactMap { URL(string: $0)?.host })

class App: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate {
    var fenster: NSWindow!
    var web: WKWebView!

    func applicationDidFinishLaunching(_ n: Notification) {
        web = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        web.navigationDelegate = self
        web.uiDelegate = self
        fenster = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1040, height: 860),
                           styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        fenster.title = NAME
        fenster.minSize = NSSize(width: 420, height: 520)
        fenster.contentView = web
        fenster.delegate = self
        fenster.center()
        fenster.setFrameAutosaveName("TKPreisjaegerFenster")
        fenster.makeKeyAndOrderFront(nil)
        menue()
        verbinden()
        NSApp.activate(ignoringOtherApps: true)
    }

    func menue() {
        let haupt = NSMenu()
        let a = NSMenuItem(); haupt.addItem(a)
        let am = NSMenu()
        am.addItem(withTitle: "Über \(NAME)", action: #selector(ueber), keyEquivalent: "")
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
        cm.addItem(withTitle: "Neue Suche", action: #selector(neueSuche), keyEquivalent: "l")
        cm.addItem(withTitle: "Neu laden", action: #selector(neuLaden), keyEquivalent: "r")
        c.submenu = cm
        NSApp.mainMenu = haupt
    }

    // Erste erreichbare Adresse nehmen (Heimnetz, sonst Tailnet)
    func verbinden(_ nr: Int = 0) {
        guard nr < ADRESSEN.count, let u = URL(string: ADRESSEN[nr] + "/api/stand") else { return keineVerbindung() }
        var r = URLRequest(url: u); r.timeoutInterval = 3
        URLSession.shared.dataTask(with: r) { d, antwort, _ in
            DispatchQueue.main.async {
                if (antwort as? HTTPURLResponse)?.statusCode == 200, d != nil {
                    self.web.load(URLRequest(url: URL(string: ADRESSEN[nr] + "/")!))
                } else {
                    self.verbinden(nr + 1)
                }
            }
        }.resume()
    }

    func keineVerbindung() {
        web.loadHTMLString("""
        <meta charset="utf-8"><body style="font:16px -apple-system;margin:70px auto;max-width:460px;text-align:center;color:#444">
        <h2>TK Preisjäger ist nicht erreichbar</h2>
        <p>Der HP antwortet nicht. Ist der Mac im Heimnetz oder Tailscale eingeschaltet?</p>
        <p><a href="preisjaeger://neu" style="display:inline-block;padding:10px 22px;background:#0b7a53;color:#fff;border-radius:10px;text-decoration:none">Erneut versuchen</a></p></body>
        """, baseURL: nil)
    }

    @objc func ueber() {
        let m = NSAlert()
        m.messageText = NAME
        m.informativeText = "Fassung 1.1\nFindet für genau ein Produkt den günstigsten Preis – neu und gebraucht.\n\n© 2026 Tekin Kaplan. Alle Rechte vorbehalten."
        m.runModal()
    }
    @objc func neuLaden() { if web.url?.scheme?.hasPrefix("http") == true { web.reload() } else { verbinden() } }
    @objc func neueSuche() { web.evaluateJavaScript("var q=document.getElementById('q'); if(q){q.focus();q.select();scrollTo(0,0)}") }

    // Eigene Seiten im Fenster, alles andere (Angebote) im normalen Browser
    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let u = a.request.url else { return decisionHandler(.cancel) }
        if u.scheme == "preisjaeger" { verbinden(); return decisionHandler(.cancel) }
        if u.scheme == "about" || (u.host != nil && EIGENE.contains(u.host!)) { return decisionHandler(.allow) }
        if a.navigationType == .linkActivated || a.targetFrame == nil { NSWorkspace.shared.open(u); return decisionHandler(.cancel) }
        decisionHandler(a.targetFrame?.isMainFrame == true ? .cancel : .allow)
    }
    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url { NSWorkspace.shared.open(u) }
        return nil
    }
    // Dateiauswahl (Fotos für „Verkaufen“): ohne diese Funktion öffnet WebKit keinen Auswahldialog
    func webView(_ w: WKWebView, runOpenPanelWith p: WKOpenPanelParameters, initiatedByFrame f: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = p.allowsMultipleSelection
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.beginSheetModal(for: fenster) { antwort in completionHandler(antwort == .OK ? panel.urls : nil) }
    }
    func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) { keineVerbindung() }

    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
let d = App()
app.delegate = d
app.setActivationPolicy(.regular)
app.run()
