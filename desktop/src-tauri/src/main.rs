// Dockbench desktop shell.
//
// Its whole job: start the bundled engine, learn the port and session token
// it chose, hand those to the webview, and make sure the engine dies with
// the app.
//
// The UI is the existing frontend/ folder, unmodified — this is a shell
// around the same app, not a fork of it. The difference the user sees is
// that the seven server-assisted tools (OCR, full-fidelity Office
// conversion, Ghostscript compression, PDF/A, background removal, chat)
// light up, because there is now an engine answering on loopback. Nothing
// leaves the machine.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader};
use std::sync::Mutex;

use tauri::{Manager, RunEvent, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Handle to the engine child process, so it can be killed on exit.
struct Engine(Mutex<Option<CommandChild>>);

/// What the webview needs in order to talk to the engine.
#[derive(Clone, serde::Serialize)]
struct EngineInfo {
    port: u16,
    token: String,
}

#[tauri::command]
fn engine_info(state: State<'_, Mutex<Option<EngineInfo>>>) -> Option<EngineInfo> {
    state.lock().ok().and_then(|g| g.clone())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Engine(Mutex::new(None)))
        .manage(Mutex::<Option<EngineInfo>>::new(None))
        .invoke_handler(tauri::generate_handler![engine_info])
        .setup(|app| {
            let handle = app.handle().clone();

            // `dockbench-engine` is the PyInstaller-frozen backend, declared
            // as an externalBin in tauri.conf.json. Tauri resolves the
            // platform-specific binary name for us.
            let (mut rx, child) = app
                .shell()
                .sidecar("dockbench-engine")
                .expect("dockbench-engine sidecar is missing from the bundle")
                .spawn()
                .expect("failed to start the local engine");

            app.state::<Engine>().0.lock().unwrap().replace(child);

            // The engine prints exactly one handshake line on stdout:
            //     DOCKBENCH_READY <port> <token>
            // Read asynchronously; blocking here would freeze the UI thread
            // before the window is even shown.
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stdout(line) = event {
                        let line = String::from_utf8_lossy(&line).trim().to_string();
                        if let Some(rest) = line.strip_prefix("DOCKBENCH_READY ") {
                            let mut parts = rest.split_whitespace();
                            let port: u16 = match parts.next().and_then(|p| p.parse().ok()) {
                                Some(p) => p,
                                None => continue,
                            };
                            let token = match parts.next() {
                                Some(t) => t.to_string(),
                                None => continue,
                            };

                            let info = EngineInfo { port, token: token.clone() };
                            handle
                                .state::<Mutex<Option<EngineInfo>>>()
                                .lock()
                                .unwrap()
                                .replace(info.clone());

                            // Point the existing frontend at the local engine.
                            // These are the same two keys a user would set by
                            // hand to aim the web app at a self-hosted backend;
                            // we are just filling them in automatically.
                            let js = format!(
                                r#"try{{
                                     localStorage.setItem('dockbench.apiBase','http://127.0.0.1:{port}');
                                     localStorage.setItem('dockbench.apiToken','{token}');
                                     window.dispatchEvent(new Event('dockbench-engine-ready'));
                                   }}catch(e){{}}"#
                            );
                            if let Some(win) = handle.get_webview_window("main") {
                                let _ = win.eval(&js);
                            }
                        }
                    }
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building the Dockbench app")
        .run(|app_handle, event| {
            // Never leave an orphaned engine listening on loopback.
            if let RunEvent::ExitRequested { .. } | RunEvent::Exit = event {
                if let Some(child) = app_handle.state::<Engine>().0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        });
}
