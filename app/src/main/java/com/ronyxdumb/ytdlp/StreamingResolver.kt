package com.ronyxdumb.ytdlp

import java.net.URI
import java.net.URLDecoder
import java.net.URLEncoder
import java.util.Base64
import org.json.JSONObject
import org.jsoup.Jsoup
import java.net.HttpURLConnection
import java.net.URL

/** Resolves only public watch pages. Never evaluates remote JavaScript. */
object StreamingResolver {
    const val USER_AGENT = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"
    private val playerHosts = setOf("vixcloud.co", "vixcloud.cc")
    private fun isPlayerUrl(url: String): Boolean = runCatching {
        val uri = URI(url)
        uri.scheme?.lowercase() in setOf("http", "https") &&
            uri.host?.lowercase() in playerHosts && Regex("/embed/\\d+/?").matches(uri.path.orEmpty())
    }.getOrDefault(false)

    internal fun findPlayerUrl(html: String, baseUrl: String): String =
        Jsoup.parse(html, baseUrl).select("iframe[src]").map { it.absUrl("src") }
            .firstOrNull { isPlayerUrl(it) }
            ?: error("Il sito non ha fornito un player pubblico VixCloud.")

    data class Result(val url: String, val referer: String, val title: String)
    private fun URI.getQueryParameter(name: String): String? = rawQuery?.split('&')?.map { it.split('=', limit = 2) }?.firstOrNull {
        URLDecoder.decode(it[0], "UTF-8") == name
    }?.let { URLDecoder.decode(it.getOrElse(1) { "" }, "UTF-8") }
    private class QueryBuilder(private val uri: URI) {
        private val params = mutableListOf<String>()
        fun appendQueryParameter(key: String, value: String): QueryBuilder {
            params += URLEncoder.encode(key, "UTF-8") + "=" + URLEncoder.encode(value, "UTF-8")
            return this
        }
        fun build(): String {
            val base = uri.toString().substringBefore('#')
            return base + (if (uri.rawQuery == null) "?" else "&") + params.joinToString("&")
        }
    }
    fun supports(url: String): Boolean = runCatching {
        val uri = URI(url)
        val host = uri.host?.lowercase().orEmpty()
        uri.scheme?.lowercase() in setOf("http", "https") &&
            (((host.startsWith("streamingcommunity") || host.startsWith("www.streamingcommunity")) &&
                Regex("/(?:[a-z]{2}/)?(?:watch|iframe)/\\d+/?").matches(uri.path.orEmpty())) || isPlayerUrl(url))
    }.getOrDefault(false)
    private class Session(private val cancelled: () -> Boolean) {
        private val cookies = mutableMapOf<String, MutableMap<String, String>>()
        fun get(url: String, referer: String? = null): String {
            var current = url
            repeat(6) {
                if (cancelled()) throw InterruptedException()
                val parsed = URL(current)
                require(parsed.protocol in listOf("https", "http")) { "Protocollo player non supportato" }
                val conn = parsed.openConnection() as HttpURLConnection
                conn.connectTimeout = 20000; conn.readTimeout = 20000; conn.instanceFollowRedirects = false
                conn.setRequestProperty("User-Agent", USER_AGENT)
                conn.setRequestProperty("Cache-Control", "no-cache")
                referer?.let { conn.setRequestProperty("Referer", it) }
                cookies[parsed.host]?.takeIf { it.isNotEmpty() }?.let { conn.setRequestProperty("Cookie", it.entries.joinToString("; ") { e -> "${e.key}=${e.value}" }) }
                try {
                    val code = conn.responseCode
                    conn.headerFields.entries.filter { it.key.equals("Set-Cookie", true) }.flatMap { it.value ?: emptyList() }.forEach {
                        val pair = it.substringBefore(';').split('=', limit = 2)
                        if (pair.size == 2) cookies.getOrPut(parsed.host) { mutableMapOf() }[pair[0]] = pair[1]
                    }
                    if (code in listOf(301, 302, 303, 307, 308)) {
                        current = URL(parsed, conn.getHeaderField("Location") ?: error("Redirect senza destinazione")).toString()
                    } else {
                        check(code in 200..299) { "Il player ha risposto HTTP $code. Riprova o verifica il link nel browser." }
                        val result = conn.inputStream.bufferedReader().use { reader ->
                            val buffer = CharArray(8192); val text = StringBuilder()
                            while (true) {
                                if (cancelled()) throw InterruptedException()
                                val count = reader.read(buffer); if (count < 0) break
                                text.append(buffer, 0, count)
                                check(text.length <= 4_000_000) { "Pagina del player troppo grande" }
                            }
                            text.toString()
                        }
                        return result
                    }
                } finally { conn.disconnect() }
            }
            error("Troppi redirect del player")
        }
    }
    fun resolve(url: String, cancelled: () -> Boolean): Result {
        val session = Session(cancelled)
        var playerUrl = url
        var title = "Video"
        if (!isPlayerUrl(url)) {
            val requestUrl = if (Regex("/(?:[a-z]{2}/)?iframe/\\d+/?").matches(URI(url).path.orEmpty())) {
                QueryBuilder(URI(url)).appendQueryParameter("_ytdlp", System.currentTimeMillis().toString()).build()
            } else url
            val doc = Jsoup.parse(session.get(requestUrl), url)
            val pageData = doc.selectFirst("[data-page]")?.attr("data-page")
            val props = pageData?.let { JSONObject(it).getJSONObject("props") }
            if (props != null) {
                check(!props.optBoolean("redirectToLogin")) { "Questa pagina richiede autenticazione; non supportata dall'app." }
                title = props.optJSONObject("title")?.optString("name", "Video") ?: "Video"
                val episode = props.optJSONObject("episode")
                if (episode != null) title += " - ${episode.optString("name", "Episodio")}" 
                val embed = props.optString("embedUrl")
                check(embed.isNotBlank()) { "La pagina non contiene l'indirizzo del player." }
                playerUrl = URL(URL(url), embed).toString()
            } else {
                playerUrl = findPlayerUrl(doc.outerHtml(), url)
            }
            if (!isPlayerUrl(playerUrl)) {
                // Fresh request avoids an expired signed embed cached by intermediaries.
                val fresh = QueryBuilder(URI(playerUrl)).appendQueryParameter("_ytdlp", System.currentTimeMillis().toString()).build()
                playerUrl = findPlayerUrl(session.get(fresh, url), playerUrl)
            }
        }
        val html = session.get(playerUrl, url)
        return parsePlayer(html, playerUrl, title)
    }
    internal fun parsePlayer(html: String, playerUrl: String, initialTitle: String): Result {
        check(isPlayerUrl(playerUrl)) { "Indirizzo player inatteso" }
        var title = initialTitle
        val config = Regex("window\\.masterPlaylist\\s*=\\s*\\{\\s*params\\s*:\\s*\\{([\\s\\S]*?)\\}\\s*,\\s*url\\s*:\\s*['\"]([^'\"]+)['\"]").find(html)
            ?: error("Configurazione VixCloud non riconosciuta: il sito potrebbe aver cambiato player.")
        val playlist = URI(config.groupValues[2].replace("\\/", "/"))
        check(playlist.scheme?.lowercase() in setOf("https", "http") && playlist.host?.lowercase() in playerHosts &&
            Regex("/playlist/\\d+/?").matches(playlist.path.orEmpty())) { "Destinazione playlist inattesa" }
        val builder = QueryBuilder(playlist)
        val params = Regex("['\"]([a-zA-Z0-9_]+)['\"]\\s*:\\s*['\"]([^'\"]*)['\"]").findAll(config.groupValues[1])
        var tokenFound = false
        params.forEach {
            if (it.groupValues[2].isNotBlank()) {
                builder.appendQueryParameter(it.groupValues[1], it.groupValues[2])
                if (it.groupValues[1] == "token") tokenFound = true
            }
        }
        check(tokenFound) { "Token del player mancante" }
        val embedUri = URI(playerUrl)
        if (!embedUri.getQueryParameter("canPlayFHD").isNullOrEmpty()) builder.appendQueryParameter("h", "1")
        if (!embedUri.getQueryParameter("scz").isNullOrEmpty()) builder.appendQueryParameter("scz", "1")
        builder.appendQueryParameter("lang", embedUri.getQueryParameter("lang") ?: "en")
        if (title == "Video") {
            embedUri.getQueryParameter("t")?.let { encoded ->
                runCatching { title = String(Base64.getDecoder().decode(encoded), Charsets.UTF_8) }
            }
        }
        return Result(builder.build(), playerUrl, title)
    }
}
