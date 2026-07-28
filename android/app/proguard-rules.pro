# The WebView bridge is reached reflectively by the framework.
-keepclassmembers class in.co.pdflove.** {
    public *;
}
-keepattributes JavascriptInterface
