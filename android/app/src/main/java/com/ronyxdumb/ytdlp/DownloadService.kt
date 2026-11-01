package com.ronyxdumb.ytdlp

import android.app.*
import android.content.*
import android.os.*
import android.provider.MediaStore
import androidx.core.app.NotificationCompat
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import com.yausername.ffmpeg.FFmpeg
import java.io.File
import java.util.concurrent.Executors

object DownloadState {
    @Volatile var busy = false
    @Volatile var progress = 0
    @Volatile var message = "Incolla un link per iniziare"
    @Volatile var cancelled = false
}

class DownloadService : Service() {
    private val executor = Executors.newSingleThreadExecutor()
    private val processId = "download"
    private var wakeLock: PowerManager.WakeLock? = null
    override fun onBind(intent: Intent?) = null
    override fun onCreate() {
        super.onCreate()
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel("downloads", "Download video", NotificationManager.IMPORTANCE_LOW))
    }
    private fun notification(text: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val cancel = PendingIntent.getService(this, 1, Intent(this, DownloadService::class.java).setAction("cancel"), PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, "downloads").setSmallIcon(com.ronyxdumb.ytdlp.R.drawable.ic_download)
            .setContentTitle("YtDlp").setContentText(text).setContentIntent(open).setOnlyAlertOnce(true)
            .setOngoing(true).setProgress(100, DownloadState.progress, DownloadState.progress == 0)
            .addAction(0, "Annulla", cancel).build()
    }
    private fun report(text: String, progress: Int = DownloadState.progress) {
        DownloadState.message = text; DownloadState.progress = progress
        getSystemService(NotificationManager::class.java).notify(1, notification(text))
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "cancel") {
            DownloadState.cancelled = true
            YoutubeDL.getInstance().destroyProcessById(processId)
            return START_NOT_STICKY
        }
        if (DownloadState.busy) return START_NOT_STICKY
        val url = intent?.getStringExtra("url") ?: return START_NOT_STICKY
        DownloadState.busy = true; DownloadState.cancelled = false; DownloadState.progress = 0
        startForeground(1, notification("Preparazione…"))
        wakeLock = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "YtDlp:download").apply { acquire(6 * 60 * 60 * 1000L) }
        executor.execute {
            val directory = File(filesDir, "staging").apply { mkdirs() }
            try {
                directory.listFiles()?.forEach { it.delete() }
                report("Preparazione del motore…")
                YoutubeDL.getInstance().init(this)
                FFmpeg.getInstance().init(this)
                if (DownloadState.cancelled) throw InterruptedException()
                val resolved = if (StreamingResolver.supports(url)) {
                    report("Riconoscimento del player VixCloud…")
                    StreamingResolver.resolve(url) { DownloadState.cancelled }
                } else null
                val request = YoutubeDLRequest(resolved?.url ?: url)
                if (resolved != null) {
                    request.addOption("--referer", resolved.referer)
                    request.addOption("--user-agent", StreamingResolver.USER_AGENT)
                    request.addOption("--force-generic-extractor")
                }
                request.addOption("--no-playlist")
                request.addOption("--no-mtime")
                request.addOption("--restrict-filenames")
                request.addOption("--trim-filenames", "160")
                request.addOption("--socket-timeout", "30")
                request.addOption("-f", (if (resolved != null && java.net.URI(resolved.url).rawQuery.contains("lang=it")) "bv[vcodec^=avc1]+ba[format_id=audio-Italian]/" else "") + "bv[vcodec^=avc1]+ba[acodec^=mp4a]/b[vcodec^=avc1][acodec^=mp4a]/bv*[ext=mp4]+ba[ext=m4a]/bv*[ext=mp4]+ba[ext=mp4]/b[ext=mp4]/bv*+ba/b")
                request.addOption("--merge-output-format", "mp4")
                val template = if (resolved != null) {
                    val safeTitle = resolved.title.replace(Regex("[^\\p{L}\\p{N} ._-]"), "_").take(120).ifBlank { "Video" }.replace("%", "_")
                    "${directory.absolutePath}/$safeTitle.%(ext)s"
                } else "${directory.absolutePath}/%(title).120s [%(id)s].%(ext)s"
                request.addOption("-o", template)
                report("Download in corso…")
                YoutubeDL.getInstance().execute(request, processId) { percent, eta, _ ->
                    report("Download ${percent.toInt()}% · ${eta}s rimanenti", percent.toInt().coerceIn(0, 100))
                }
                if (DownloadState.cancelled) throw InterruptedException()
                val files = directory.listFiles()?.filter { it.isFile && it.extension !in listOf("part", "ytdl", "temp") } ?: emptyList()
                check(files.isNotEmpty()) { "Nessun video prodotto dal sito." }
                report("Salvataggio in Download/YtDlp…", 100)
                for (file in files) {
                    if (DownloadState.cancelled) throw InterruptedException()
                    val mime = when(file.extension.lowercase()) { "mp4" -> "video/mp4"; "webm" -> "video/webm"; "mkv" -> "video/x-matroska"; else -> "application/octet-stream" }
                    val values = ContentValues().apply {
                        put(MediaStore.Downloads.DISPLAY_NAME, file.name)
                        put(MediaStore.Downloads.MIME_TYPE, mime)
                        put(MediaStore.Downloads.RELATIVE_PATH, "Download/YtDlp/")
                        put(MediaStore.Downloads.IS_PENDING, 1)
                    }
                    val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values) ?: error("Impossibile creare il file in Download.")
                    try {
                        val output = contentResolver.openOutputStream(uri) ?: error("Impossibile aprire il file.")
                        output.use { out -> file.inputStream().use { input ->
                            val buffer = ByteArray(65536)
                            while (true) {
                                if (DownloadState.cancelled) throw InterruptedException()
                                val count = input.read(buffer); if (count < 0) break
                                out.write(buffer, 0, count)
                            }
                        } }
                        contentResolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
                    } catch (e: Exception) { contentResolver.delete(uri, null, null); throw e }
                }
                DownloadState.message = "✓ Salvato in Download/YtDlp/"
                DownloadState.progress = 100
            } catch (e: Exception) {
                DownloadState.message = if (DownloadState.cancelled) "Download annullato" else "Errore: ${e.message?.replace(Regex("https?://[^\\s]+"), "[indirizzo video]")?.takeLast(1500) ?: "download non riuscito"}"
            } finally {
                directory.listFiles()?.forEach { it.delete() }
                DownloadState.busy = false
                wakeLock?.let { if (it.isHeld) it.release() }
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }
    override fun onTimeout(startId: Int, fgsType: Int) {
        DownloadState.cancelled = true
        YoutubeDL.getInstance().destroyProcessById(processId)
        DownloadState.message = "Tempo massimo di download raggiunto"
        stopForeground(STOP_FOREGROUND_REMOVE); stopSelf()
    }
    override fun onDestroy() { executor.shutdown(); super.onDestroy() }
}
