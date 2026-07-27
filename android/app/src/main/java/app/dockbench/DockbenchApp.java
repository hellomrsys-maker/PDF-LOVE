package app.dockbench;

import android.app.Application;
import android.os.Build;
import android.webkit.WebView;

/**
 * Application entry point.
 *
 * Exists for one reason: on Android P and above, every WebView in a process
 * must use a distinct data directory, and the default is only safe when a
 * single process uses it. Naming it explicitly avoids a crash if the app
 * ever gains a second process (a share target, a widget).
 */
public class DockbenchApp extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            String process = getProcessName();
            if (!getPackageName().equals(process)) {
                WebView.setDataDirectorySuffix(process);
            }
        }
    }
}
