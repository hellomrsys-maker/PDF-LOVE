package app.dockbench;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.content.Intent;

import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.webkit.WebViewAssetLoader;

/**
 * Hosts the Dockbench web app entirely from assets bundled in the APK.
 *
 * The app is served through {@link WebViewAssetLoader} rather than a
 * {@code file://} URL. That matters more than it looks: assets are handed to
 * the WebView on an {@code https://appassets.androidplatform.net/} origin, so
 * the page runs in a secure context. Camera access, the service worker and
 * WebCrypto all refuse to operate on {@code file://}, which would have
 * silently disabled the scanner, offline caching and licence verification.
 *
 * No network request is made to load the app. Everything is local.
 */
public class MainActivity extends AppCompatActivity {

    /** Origin the bundled assets are served from. */
    private static final String APP_ORIGIN = "https://appassets.androidplatform.net";
    private static final String START_URL = APP_ORIGIN + "/assets/www/index.html";

    private WebView webView;
    private WebViewAssetLoader assetLoader;

    /** Pending getUserMedia request, held while the OS permission dialog is up. */
    private PermissionRequest pendingCameraRequest;
    private ActivityResultLauncher<String> cameraPermissionLauncher;

    /** Pending <input type="file"> callback. */
    private ValueCallback<Uri[]> pendingFileCallback;
    private ActivityResultLauncher<Intent> filePickerLauncher;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        registerLaunchers();

        assetLoader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        webView = new WebView(this);
        setContentView(webView);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // localStorage: favourites, licence, settings
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);   // camera preview starts on tap
        s.setSupportZoom(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        // Never allow the page to reach the device filesystem directly; every
        // asset it needs comes through the loader above.
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            s.setSafeBrowsingEnabled(true);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                return assetLoader.shouldInterceptRequest(req.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri url = req.getUrl();
                // In-app navigation stays in the WebView; anything else (an ad
                // click, a link to the site) opens in the user's browser rather
                // than pretending to still be the app.
                if (APP_ORIGIN.equals(url.getScheme() + "://" + url.getAuthority())) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, url));
                } catch (Exception ignored) {
                    // No handler for the scheme; swallow rather than crash.
                }
                return true;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                // Only the camera is ever granted, and only after the OS has
                // asked the user. Everything else is refused outright.
                for (String r : request.getResources()) {
                    if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(r)) {
                        pendingCameraRequest = request;
                        if (ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.CAMERA)
                                == PackageManager.PERMISSION_GRANTED) {
                            grantCamera();
                        } else {
                            cameraPermissionLauncher.launch(Manifest.permission.CAMERA);
                        }
                        return;
                    }
                }
                request.deny();
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (pendingFileCallback != null) {
                    pendingFileCallback.onReceiveValue(null);
                }
                pendingFileCallback = callback;
                try {
                    filePickerLauncher.launch(params.createIntent());
                    return true;
                } catch (Exception e) {
                    pendingFileCallback = null;
                    return false;
                }
            }
        });

        // Back button walks the app's own history before leaving.
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack();
                } else {
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                }
            }
        });

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(START_URL);
        }
    }

    private void registerLaunchers() {
        cameraPermissionLauncher = registerForActivityResult(
                new ActivityResultContracts.RequestPermission(), granted -> {
                    if (pendingCameraRequest == null) return;
                    if (granted) {
                        grantCamera();
                    } else {
                        pendingCameraRequest.deny();
                        pendingCameraRequest = null;
                    }
                });

        filePickerLauncher = registerForActivityResult(
                new ActivityResultContracts.StartActivityForResult(), result -> {
                    if (pendingFileCallback == null) return;
                    Uri[] uris = null;
                    Intent data = result.getData();
                    if (result.getResultCode() == RESULT_OK && data != null) {
                        if (data.getClipData() != null) {
                            int n = data.getClipData().getItemCount();
                            uris = new Uri[n];
                            for (int i = 0; i < n; i++) {
                                uris[i] = data.getClipData().getItemAt(i).getUri();
                            }
                        } else if (data.getData() != null) {
                            uris = new Uri[]{data.getData()};
                        }
                    }
                    pendingFileCallback.onReceiveValue(uris);
                    pendingFileCallback = null;
                });
    }

    private void grantCamera() {
        if (pendingCameraRequest == null) return;
        pendingCameraRequest.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
        pendingCameraRequest = null;
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
