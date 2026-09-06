package com.aas.keystoredemo;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import android.widget.ScrollView;
import android.graphics.Color;
import android.util.TypedValue;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.security.keystore.KeyInfo;
import java.security.KeyStore;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.SecretKeyFactory;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;

public class MainActivity extends Activity {
    static String hex(byte[] b, int max) {
        StringBuilder s = new StringBuilder();
        int n = Math.min(b.length, max);
        for (int i = 0; i < n; i++) s.append(String.format("%02x", b[i]));
        if (b.length > max) s.append("…");
        return s.toString();
    }

    @Override
    protected void onCreate(Bundle st) {
        super.onCreate(st);
        StringBuilder sb = new StringBuilder();
        String alias = "demoKey";
        try {
            // 1) AndroidKeyStore 안에 비추출 AES 키 생성
            KeyGenerator kg = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            kg.init(new KeyGenParameterSpec.Builder(alias,
                    KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build());
            SecretKey key = kg.generateKey();
            sb.append("[1] AES-256 key generated in AndroidKeyStore (alias=").append(alias).append(")\n\n");

            // 2) getEncoded() -> 키 원문 추출 시도
            byte[] raw = key.getEncoded();
            sb.append("[2] key.getEncoded() = ")
              .append(raw == null ? "null  -> RAW KEY NOT EXTRACTABLE" : hex(raw, 32))
              .append("\n\n");

            // 3) AES-GCM 암복호화 (키 원문 없이도 동작)
            String secret = "MY_SECRET_42";
            Cipher enc = Cipher.getInstance("AES/GCM/NoPadding");
            enc.init(Cipher.ENCRYPT_MODE, key);
            byte[] iv = enc.getIV();
            byte[] ct = enc.doFinal(secret.getBytes("UTF-8"));
            sb.append("[3] plaintext  = ").append(secret).append("\n");
            sb.append("    iv         = ").append(hex(iv, 12)).append("\n");
            sb.append("    ciphertext = ").append(hex(ct, 16)).append("\n");
            Cipher dec = Cipher.getInstance("AES/GCM/NoPadding");
            dec.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
            String back = new String(dec.doFinal(ct), "UTF-8");
            sb.append("    decrypted  = ").append(back)
              .append(back.equals(secret) ? "   (round-trip OK)" : "   (MISMATCH)").append("\n\n");

            // 4) 키의 보안 수준(소프트웨어 / TEE / StrongBox)
            KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
            ks.load(null);
            SecretKey k2 = (SecretKey) ks.getKey(alias, null);
            SecretKeyFactory f = SecretKeyFactory.getInstance(k2.getAlgorithm(), "AndroidKeyStore");
            KeyInfo info = (KeyInfo) f.getKeySpec(k2, KeyInfo.class);
            sb.append("[4] isInsideSecureHardware() = ").append(info.isInsideSecureHardware()).append("\n");
            int lvl = info.getSecurityLevel();
            String name;
            switch (lvl) {
                case KeyProperties.SECURITY_LEVEL_SOFTWARE: name = "SOFTWARE"; break;
                case KeyProperties.SECURITY_LEVEL_TRUSTED_ENVIRONMENT: name = "TRUSTED_ENVIRONMENT (TEE)"; break;
                case KeyProperties.SECURITY_LEVEL_STRONGBOX: name = "STRONGBOX"; break;
                default: name = "level=" + lvl;
            }
            sb.append("    getSecurityLevel()     = ").append(name).append("\n");
        } catch (Throwable t) {
            sb.append("\nERROR: ").append(t.getClass().getSimpleName()).append(": ").append(t.getMessage());
        }

        TextView tv = new TextView(this);
        tv.setText(sb.toString());
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        tv.setTextColor(Color.parseColor("#111111"));
        tv.setPadding(36, 60, 36, 36);
        tv.setTypeface(android.graphics.Typeface.MONOSPACE);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#F4F4F4"));
        sv.addView(tv);
        setContentView(sv);
    }
}
