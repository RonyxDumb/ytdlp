package com.ronyxdumb.ytdlp

import org.junit.Assert.*
import org.junit.Test
import java.net.URI

class StreamingResolverTest {
    private val fixture = """
        window.masterPlaylist = {
            params: { 'token': 'fixture-token', 'expires': '1795948517', 'asn': '' },
            url: 'https://vixcloud.co/playlist/693435',
        }
    """.trimIndent()
    @Test fun parsesPlayerAndPreservesLanguageAndFlags() {
        val result = StreamingResolver.parsePlayer(fixture, "https://vixcloud.co/embed/693435?canPlayFHD=1&scz=1&lang=it", "Spider-Man")
        assertEquals("Spider-Man", result.title)
        assertEquals("vixcloud.co", URI(result.url).host)
        assertEquals("token=fixture-token&expires=1795948517&h=1&scz=1&lang=it", URI(result.url).rawQuery)
        assertEquals("https://vixcloud.co/embed/693435?canPlayFHD=1&scz=1&lang=it", result.referer)
    }
    @Test fun decodesTitleForDirectEmbedAndDefaultsLanguage() {
        val result = StreamingResolver.parsePlayer(fixture, "https://vixcloud.co/embed/693435?t=U3BpZGVyLU1hbg%3D%3D", "Video")
        assertEquals("Spider-Man", result.title)
        assertTrue(result.url.endsWith("lang=en"))
        assertFalse(result.url.contains("h=1"))
    }
    @Test(expected = IllegalStateException::class) fun rejectsMissingToken() {
        StreamingResolver.parsePlayer(fixture.replace("'fixture-token'", "''"), "https://vixcloud.co/embed/1", "Video")
    }
    @Test(expected = IllegalStateException::class) fun rejectsUnexpectedPlaylistHost() {
        StreamingResolver.parsePlayer(fixture.replace("vixcloud.co/playlist", "example.com/playlist"), "https://vixcloud.co/embed/1", "Video")
    }
    @Test fun handlesOnlyRecognizedWatchAndEmbedPaths() {
        assertTrue(StreamingResolver.supports("https://streamingcommunityz.pictures/it/watch/363?e=1"))
        assertTrue(StreamingResolver.supports("https://vixcloud.co/embed/693435"))
        assertFalse(StreamingResolver.supports("https://youtube.com/watch?v=123"))
        assertFalse(StreamingResolver.supports("https://vixcloud.co/playlist/693435"))
    }
    @Test fun recognizesCurrentPlayerDomainAndAllReportedWatchPages() {
        for (id in listOf(2305, 778, 1979)) {
            assertTrue(StreamingResolver.supports("https://streamingcommunityz.day/it/watch/$id"))
            assertTrue(StreamingResolver.supports("https://streamingcommunityz.day/it/iframe/$id"))
        }
        assertTrue(StreamingResolver.supports("https://vixcloud.cc/embed/266148?lang=it"))
        assertFalse(StreamingResolver.supports("https://vixcloud.cc.evil.test/embed/266148"))
        assertFalse(StreamingResolver.supports("ftp://vixcloud.cc/embed/266148"))
        assertFalse(StreamingResolver.supports("https://vixcloud.cc/embed/not-an-id"))
        assertFalse(StreamingResolver.supports("not a URL"))
    }
    @Test fun findsCurrentIframeAndPreservesItsSignedParameters() {
        val player = "https://vixcloud.cc/embed/266148?token=embed-token&t=SHViaWUgSGFsbG93ZWVu&expires=1795948517&lang=it&scz=1"
        val html = """<iframe src="https://ads.example.test/embed/1"></iframe><iframe src="${player.replace("&", "&amp;")}"></iframe>"""
        assertEquals(player, StreamingResolver.findPlayerUrl(html, "https://streamingcommunityz.day/it/iframe/2305"))
    }
    @Test fun parsesCurrentPlaylistWithoutChangingItsHostOrToken() {
        val result = StreamingResolver.parsePlayer(fixture.replace("vixcloud.co", "vixcloud.cc"),
            "https://vixcloud.cc/embed/693435?lang=it&scz=1", "Hubie Halloween")
        assertEquals("vixcloud.cc", URI(result.url).host)
        assertEquals("token=fixture-token&expires=1795948517&scz=1&lang=it", URI(result.url).rawQuery)
        assertEquals("Hubie Halloween", result.title)
    }
    @Test(expected = IllegalStateException::class) fun rejectsLookalikePlaylistHost() {
        StreamingResolver.parsePlayer(fixture.replace("vixcloud.co/playlist", "vixcloud.cc.evil.test/playlist"),
            "https://vixcloud.cc/embed/1", "Video")
    }
    @Test(expected = IllegalStateException::class) fun rejectsLookalikeIframeHost() {
        StreamingResolver.findPlayerUrl("""<iframe src="https://vixcloud.cc.evil.test/embed/1"></iframe>""",
            "https://streamingcommunityz.day/it/iframe/2305")
    }
}
