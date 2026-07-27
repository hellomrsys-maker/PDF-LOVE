# The WebView bridge is reached reflectively by the framework.
-keepclassmembers class app.dockbench.** {
    public *;
}
-keepattributes JavascriptInterface
