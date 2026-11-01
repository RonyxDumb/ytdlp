package com.ronyxdumb.ytdlp

import org.junit.Assert.*
import org.junit.Test

class DownloadFormatTest {
    @Test fun audioSelectionExtractsAudioAndDoesNotMergeVideo() {
        for (format in DownloadFormat.entries.filter { it.audioOnly }) {
            val options = format.options().toMap()
            assertTrue(options.containsKey("--extract-audio"))
            assertFalse(options.containsKey("--merge-output-format"))
            assertFalse(options.containsKey("--recode-video"))
            assertEquals("0", options["--audio-quality"])
            assertTrue(options.getValue("-f")!!.endsWith("/ba/b"))
        }
        assertEquals("vorbis", DownloadFormat.OGG.options().toMap()["--audio-format"])
    }

    @Test fun videoFormatsAreEnforcedEvenForSingleStreamDownloads() {
        assertEquals("mp4", DownloadFormat.MP4.options().toMap()["--recode-video"])
        assertEquals("webm", DownloadFormat.WEBM.options().toMap()["--recode-video"])
        assertEquals("mkv", DownloadFormat.MKV.options().toMap()["--remux-video"])
        assertFalse(DownloadFormat.AUTO.options().toMap().containsKey("--recode-video"))
    }

    @Test fun italianTrackPreferenceSurvivesAudioAndVideoSelection() {
        for (format in DownloadFormat.entries) {
            assertTrue(format.options(true).toMap().getValue("-f")!!.contains("format_id=audio-Italian"))
            assertFalse(format.options(false).toMap().getValue("-f")!!.contains("format_id=audio-Italian"))
        }
    }

    @Test fun onlyFinalFilesOfTheRequestedFormatArePublished() {
        assertTrue(DownloadFormat.MP3.accepts("MP3"))
        assertFalse(DownloadFormat.MP3.accepts("mp4"))
        assertFalse(DownloadFormat.MP3.accepts("part"))
        assertFalse(DownloadFormat.AUTO.accepts("ytdl"))
        assertFalse(DownloadFormat.AUTO.accepts("temp"))
        assertTrue(DownloadFormat.AUTO.accepts("webm"))
        assertEquals("audio/mpeg", DownloadFormat.mimeFor("mp3"))
        assertEquals("audio/wav", DownloadFormat.mimeFor("wav"))
        assertEquals("audio/mp4", DownloadFormat.mimeFor("m4a"))
        assertEquals("audio/flac", DownloadFormat.mimeFor("flac"))
        assertEquals("audio/ogg", DownloadFormat.mimeFor("ogg"))
        assertEquals("video/mp4", DownloadFormat.mimeFor("mp4"))
    }

    @Test fun savedSelectionAndOldInstallationsUseStableIds() {
        assertEquals(DownloadFormat.WAV, DownloadFormat.fromId("wav"))
        assertEquals(DownloadFormat.MP4, DownloadFormat.saved(null))
        assertEquals(DownloadFormat.MP4, DownloadFormat.saved("obsolete"))
    }

    @Test(expected = IllegalArgumentException::class)
    fun externalRequestsCannotSupplyArbitraryOptionsAsAFormat() {
        DownloadFormat.fromId("--exec=anything")
    }
}
