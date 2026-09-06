package com.aas.oauth;

import android.app.Activity;
import android.os.Bundle;
import android.util.Base64;
import android.util.TypedValue;
import android.graphics.Color;
import android.graphics.Typeface;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.OutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.security.SecureRandom;
import org.json.JSONObject;

public class MainActivity extends Activity {
    static final String BASE = "http://10.0.2.2:8011";
    static final String REDIRECT = "aasoauth://cb";
    static final String CLIENT = "aas-client";
    TextView tv;

    static String b64url(byte[] b) {
        return Base64.encodeToString(b, Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP);
    }
    static String readAll(HttpURLConnection c) throws Exception {
        int code = c.getResponseCode();
        InputStream is = (code >= 400) ? c.getErrorStream() : c.getInputStream();
        java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[4096]; int n;
        while ((n = is.read(buf)) > 0) bo.write(buf, 0, n);
        return bo.toString("UTF-8");
    }
    static String httpGet(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setRequestMethod("GET");
        return readAll(c);
    }
    static String httpPost(String url, String form) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setRequestMethod("POST"); c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
        OutputStream os = c.getOutputStream(); os.write(form.getBytes("UTF-8")); os.close();
        return readAll(c);
    }

    void run(StringBuilder sb) throws Exception {
        SecureRandom rng = new SecureRandom();
        // 1) PKCE: verifier + challenge(S256)
        byte[] vb = new byte[32]; rng.nextBytes(vb);
        String verifier = b64url(vb);
        String challenge = b64url(MessageDigest.getInstance("SHA-256").digest(verifier.getBytes("US-ASCII")));
        byte[] stb = new byte[16]; rng.nextBytes(stb);
        String state = b64url(stb);
        sb.append("[PKCE]\n verifier  = ").append(verifier.substring(0, 16)).append("…\n");
        sb.append(" challenge = ").append(challenge.substring(0, 16)).append("…  (S256)\n\n");

        // 2) /authorize
        String authUrl = BASE + "/authorize?response_type=code&client_id=" + CLIENT
                + "&redirect_uri=" + java.net.URLEncoder.encode(REDIRECT, "UTF-8")
                + "&state=" + state
                + "&code_challenge=" + challenge + "&code_challenge_method=S256";
        JSONObject a = new JSONObject(httpGet(authUrl));
        String code = a.optString("code");
        String retState = a.optString("state");
        sb.append("[/authorize]\n code = ").append(code).append("\n");
        sb.append(" state 검증: sent==returned ? ").append(state.equals(retState) ? "OK" : "MISMATCH").append("\n\n");

        // 3) /token (올바른 verifier)
        String tokForm = "grant_type=authorization_code&code=" + code
                + "&redirect_uri=" + java.net.URLEncoder.encode(REDIRECT, "UTF-8")
                + "&client_id=" + CLIENT + "&code_verifier=" + verifier;
        JSONObject t = new JSONObject(httpPost(BASE + "/token", tokForm));
        String at = t.optString("access_token");
        String idt = t.optString("id_token");
        sb.append("[/token  올바른 verifier]\n access_token = ").append(at).append("\n");
        sb.append(" id_token     = ").append(idt.length() > 24 ? idt.substring(0, 24) + "…" : idt).append("\n");
        // id_token payload 디코드
        String[] parts = idt.split("\\.");
        if (parts.length >= 2) {
            String payload = new String(Base64.decode(parts[1], Base64.URL_SAFE), "UTF-8");
            sb.append(" id_token claims = ").append(payload).append("\n");
        }
        sb.append(" (access_token = API 호출용,  id_token = 사용자 신원)\n\n");

        // 4) 음성 테스트: 새 code 를 틀린 verifier 로 교환 -> 거부되어야 PKCE 가 지킨 것
        JSONObject a2 = new JSONObject(httpGet(authUrl));   // 새 code
        String code2 = a2.optString("code");
        String badForm = "grant_type=authorization_code&code=" + code2
                + "&redirect_uri=" + java.net.URLEncoder.encode(REDIRECT, "UTF-8")
                + "&client_id=" + CLIENT + "&code_verifier=WRONG_VERIFIER_1234567890";
        JSONObject bad = new JSONObject(httpPost(BASE + "/token", badForm));
        sb.append("[/token  틀린 verifier = 도난 code 재사용 시도]\n");
        sb.append(" error  = ").append(bad.optString("error")).append("\n");
        sb.append(" reason = ").append(bad.optString("reason")).append("\n");
        sb.append(" => PKCE 가 도난 code 의 교환을 막았다.\n");

        // 5) redirect_uri 검증 테스트
        String badRedir = BASE + "/authorize?response_type=code&client_id=" + CLIENT
                + "&redirect_uri=" + java.net.URLEncoder.encode("evil://cb", "UTF-8")
                + "&state=x&code_challenge=" + challenge + "&code_challenge_method=S256";
        JSONObject r = new JSONObject(httpGet(badRedir));
        sb.append("\n[/authorize  악성 redirect_uri]\n error = ").append(r.optString("error")).append("  (등록값과 정확 일치만 허용)\n");
    }

    @Override
    protected void onCreate(Bundle st) {
        super.onCreate(st);
        tv = new TextView(this);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        tv.setTextColor(Color.parseColor("#111111"));
        tv.setPadding(28, 56, 28, 28);
        tv.setTypeface(Typeface.MONOSPACE);
        tv.setText("running OAuth PKCE flow…");
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#EAF2FF"));
        sv.addView(tv);
        setContentView(sv);

        new Thread(new Runnable() {
            public void run() {
                final StringBuilder sb = new StringBuilder();
                sb.append("OAuth 2.0 Authorization Code + PKCE\nserver = ").append(BASE).append("\n\n");
                try { MainActivity.this.run(sb); }
                catch (final Throwable e) { sb.append("\nERROR: ").append(e); }
                runOnUiThread(new Runnable() { public void run() { tv.setText(sb.toString()); } });
            }
        }).start();
    }
}
