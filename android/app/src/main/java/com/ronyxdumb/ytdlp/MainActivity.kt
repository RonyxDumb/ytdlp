package com.ronyxdumb.ytdlp

import android.Manifest
import android.content.*
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.*
import android.view.*
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.*
import com.google.android.material.color.DynamicColors
import com.google.android.material.color.MaterialColors
import com.google.android.material.button.MaterialButton
import com.google.android.material.card.MaterialCardView
import com.google.android.material.progressindicator.LinearProgressIndicator
import com.google.android.material.textfield.*
import com.yausername.youtubedl_android.YoutubeDL

class MainActivity : AppCompatActivity() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var status: TextView
    private lateinit var progress: LinearProgressIndicator
    private lateinit var download: MaterialButton
    private lateinit var cancel: MaterialButton
    private lateinit var update: MaterialButton
    private lateinit var input: TextInputEditText
    private lateinit var formatField: TextInputLayout
    private lateinit var formatChoice: MaterialAutoCompleteTextView
    private var selectedFormat = DownloadFormat.MP4
    private var updating = false
    private val refresh = object : Runnable {
        override fun run() {
            if (!updating) status.text = DownloadState.message
            progress.progress = DownloadState.progress
            progress.visibility = if (DownloadState.busy) View.VISIBLE else View.GONE
            download.isEnabled = !DownloadState.busy && !updating
            update.isEnabled = !DownloadState.busy && !updating
            formatField.isEnabled = !DownloadState.busy && !updating
            cancel.visibility = if (DownloadState.busy) View.VISIBLE else View.GONE
            handler.postDelayed(this, 400)
        }
    }
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
    override fun onCreate(savedInstanceState: Bundle?) {
        DynamicColors.applyToActivityIfAvailable(this)
        super.onCreate(savedInstanceState)
        selectedFormat = DownloadFormat.saved(savedInstanceState?.getString(DownloadFormat.EXTRA)
            ?: getSharedPreferences("settings", MODE_PRIVATE).getString(DownloadFormat.EXTRA, null))
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = Color.TRANSPARENT; window.navigationBarColor = Color.TRANSPARENT
        window.isNavigationBarContrastEnforced = false
        val light = resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK != Configuration.UI_MODE_NIGHT_YES
        WindowCompat.getInsetsController(window, window.decorView).apply { isAppearanceLightStatusBars = light; isAppearanceLightNavigationBars = light }
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(24), 0, dp(24), 0); setBackgroundColor(MaterialColors.getColor(this, com.google.android.material.R.attr.colorSurface)) }
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            view.setPadding(dp(24) + bars.left, dp(24) + bars.top, dp(24) + bars.right, dp(24) + bars.bottom); insets
        }
        fun text(value: String, size: Float) = TextView(this).apply { text = value; textSize = size; setTextColor(MaterialColors.getColor(root, com.google.android.material.R.attr.colorOnSurface)); setPadding(0, dp(8), 0, dp(12)) }
        root.addView(text("↓", 48f))
        root.addView(text("YtDlp", 36f))
        root.addView(text("Il tuo prossimo video, offline.", 18f))
        val card = MaterialCardView(this).apply { radius = dp(28).toFloat(); strokeWidth = 0; setCardBackgroundColor(MaterialColors.getColor(root, com.google.android.material.R.attr.colorSurfaceContainer)) }
        val content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(20), dp(20), dp(20)) }
        content.addView(text("Incolla il link", 22f))
        val field = TextInputLayout(this).apply { hint = "https://…"; boxBackgroundMode = TextInputLayout.BOX_BACKGROUND_OUTLINE; setBoxCornerRadii(dp(16).toFloat(), dp(16).toFloat(), dp(16).toFloat(), dp(16).toFloat()) }
        input = TextInputEditText(field.context).apply { inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI; maxLines = 3 }
        field.addView(input); content.addView(field)
        val paste = MaterialButton(this, null, com.google.android.material.R.attr.materialButtonOutlinedStyle).apply { text = "Incolla dagli appunti"; setOnClickListener {
            val clip = (getSystemService(CLIPBOARD_SERVICE) as ClipboardManager).primaryClip
            if (clip != null && clip.itemCount > 0) input.setText(clip.getItemAt(0).coerceToText(this@MainActivity))
        } }
        content.addView(paste)
        formatField = TextInputLayout(this).apply {
            hint = "Formato del download"
            boxBackgroundMode = TextInputLayout.BOX_BACKGROUND_OUTLINE
            endIconMode = TextInputLayout.END_ICON_DROPDOWN_MENU
            helperText = selectedFormat.description
        }
        formatChoice = MaterialAutoCompleteTextView(formatField.context).apply {
            inputType = android.text.InputType.TYPE_NULL
            setSimpleItems(DownloadFormat.entries.map { it.label }.toTypedArray())
            setText(selectedFormat.label, false)
            setOnItemClickListener { _, _, position, _ ->
                selectedFormat = DownloadFormat.entries[position]
                formatField.helperText = selectedFormat.description
                download.text = if (selectedFormat.audioOnly) "Scarica audio" else "Scarica video"
                getSharedPreferences("settings", MODE_PRIVATE).edit()
                    .putString(DownloadFormat.EXTRA, selectedFormat.id).apply()
            }
        }
        formatField.addView(formatChoice)
        content.addView(formatField, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12); bottomMargin = dp(12) })
        download = MaterialButton(this).apply { text = if (selectedFormat.audioOnly) "Scarica audio" else "Scarica video"; cornerRadius = dp(24); setOnClickListener { startDownload() } }
        content.addView(download, LinearLayout.LayoutParams(-1, dp(56)))
        content.addView(text("Cartella: Download/YtDlp/", 14f))
        card.addView(content); root.addView(card, LinearLayout.LayoutParams(-1, -2))
        status = text(DownloadState.message, 16f); status.setTextIsSelectable(true); root.addView(status)
        progress = LinearProgressIndicator(this); root.addView(progress)
        cancel = MaterialButton(this, null, com.google.android.material.R.attr.materialButtonOutlinedStyle).apply { text = "Annulla download"; setOnClickListener { startService(Intent(this@MainActivity, DownloadService::class.java).setAction("cancel")) } }; root.addView(cancel)
        update = MaterialButton(this, null, com.google.android.material.R.attr.borderlessButtonStyle).apply { text = "Aggiorna yt-dlp"; setOnClickListener {
            if (DownloadState.busy || updating) return@setOnClickListener
            updating = true; status.text = "Aggiornamento del motore…"
            Thread {
                val result = try { YoutubeDL.getInstance().init(this@MainActivity); YoutubeDL.getInstance().updateYoutubeDL(this@MainActivity); "Motore yt-dlp aggiornato" } catch (e: Exception) { "Aggiornamento fallito: ${e.message}" }
                runOnUiThread { updating = false; DownloadState.message = result; status.text = result }
            }.start()
        } }; root.addView(update)
        val scroll = ScrollView(this).apply { isFillViewport = true; addView(root) }; setContentView(scroll)
        input.setText(savedInstanceState?.getString("url") ?: intent.getStringExtra(Intent.EXTRA_TEXT) ?: "")
    }
    private fun startDownload() {
        if (DownloadState.busy || updating) return
        val url = input.text.toString().trim()
        val uri = Uri.parse(url)
        if (uri.scheme !in listOf("https", "http") || uri.host.isNullOrBlank() || url.any { it.isWhitespace() }) { input.error = "Inserisci un link HTTP o HTTPS valido"; return }
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 10)
        startForegroundService(Intent(this, DownloadService::class.java).putExtra("url", url)
            .putExtra(DownloadFormat.EXTRA, selectedFormat.id))
    }
    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("url", input.text.toString())
        outState.putString(DownloadFormat.EXTRA, selectedFormat.id)
        super.onSaveInstanceState(outState)
    }
    override fun onResume() { super.onResume(); handler.post(refresh) }
    override fun onPause() { handler.removeCallbacks(refresh); super.onPause() }
}
