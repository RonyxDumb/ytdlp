package com.ronyxdumb.ytdlp

enum class DownloadFormat(
    val id: String,
    val label: String,
    val extension: String?,
    val mimeType: String?,
    val audioOnly: Boolean,
    val description: String
) {
    MP4("mp4", "Video · MP4", "mp4", "video/mp4", false,
        "Video e audio. Conversione in MP4 se necessaria."),
    MKV("mkv", "Video · MKV", "mkv", "video/x-matroska", false,
        "Video e audio nel contenitore MKV, senza ricodifica."),
    WEBM("webm", "Video · WebM", "webm", "video/webm", false,
        "Video e audio. La conversione in WebM può richiedere tempo."),
    AUTO("auto", "Video · Automatico", null, null, false,
        "Formato scelto dal sito e da yt-dlp, senza conversione forzata."),
    MP3("mp3", "Solo audio · MP3", "mp3", "audio/mpeg", true,
        "Solo audio, qualità variabile migliore. Conversione se necessaria."),
    WAV("wav", "Solo audio · WAV", "wav", "audio/wav", true,
        "Audio PCM non compresso: file grandi, qualità della sorgente."),
    M4A("m4a", "Solo audio · M4A", "m4a", "audio/mp4", true,
        "Solo audio in M4A, con conversione AAC se necessaria."),
    FLAC("flac", "Solo audio · FLAC", "flac", "audio/flac", true,
        "Compressione senza perdita; non migliora la qualità della sorgente."),
    OPUS("opus", "Solo audio · Opus", "opus", "audio/ogg", true,
        "Solo audio con compressione Opus."),
    OGG("ogg", "Solo audio · OGG", "ogg", "audio/ogg", true,
        "Solo audio Vorbis nel contenitore OGG.");

    fun options(italian: Boolean = false): List<Pair<String, String?>> {
        val preferredAudio = if (italian) "ba[format_id=audio-Italian]/" else ""
        if (audioOnly) return listOf(
            "-f" to "${preferredAudio}ba[language^=it]/ba/b",
            "--extract-audio" to null,
            "--audio-format" to if (this == OGG) "vorbis" else id,
            "--audio-quality" to "0"
        )
        val preferredVideo = if (italian) "bv*+ba[format_id=audio-Italian]/" else ""
        val result = mutableListOf<Pair<String, String?>>("-f" to "${preferredVideo}bv*+ba[language^=it]/bv*+ba/b")
        when (this) {
            MP4 -> result.addAll(listOf("-S" to "vcodec:h264,acodec:aac,ext:mp4:m4a",
                "--merge-output-format" to "mp4/mkv", "--recode-video" to "mp4"))
            MKV -> result.addAll(listOf("--merge-output-format" to "mkv", "--remux-video" to "mkv"))
            WEBM -> result.addAll(listOf("-S" to "vcodec:vp9,acodec:opus,ext:webm",
                "--merge-output-format" to "webm/mkv", "--recode-video" to "webm"))
            else -> Unit
        }
        return result
    }

    fun accepts(extension: String): Boolean = if (this == AUTO) {
        extension.lowercase() in setOf("mp4", "mkv", "webm", "mov", "flv", "avi", "3gp", "ts", "m4v", "ogv")
    } else this.extension.equals(extension, ignoreCase = true)

    companion object {
        const val EXTRA = "format"

        fun fromId(id: String?): DownloadFormat = entries.firstOrNull { it.id == id }
            ?: throw IllegalArgumentException("Formato di download non supportato")

        fun saved(id: String?): DownloadFormat = entries.firstOrNull { it.id == id } ?: MP4

        fun mimeFor(extension: String): String = entries.firstOrNull {
            it.extension.equals(extension, ignoreCase = true)
        }?.mimeType ?: when (extension.lowercase()) {
            "mov" -> "video/quicktime"
            "avi" -> "video/x-msvideo"
            "flv" -> "video/x-flv"
            "3gp" -> "video/3gpp"
            "ts" -> "video/mp2t"
            "m4v" -> "video/mp4"
            "ogv" -> "video/ogg"
            else -> "application/octet-stream"
        }
    }
}
