# Verifica YtDlp Android 1.2

Data: 29/10/2026 19:33 CET.

## Correzione

La versione 1.1 accettava soltanto `vixcloud.co`. Tutti e tre i link segnalati incorporano player `vixcloud.cc`: questo fermava il resolver prima della playlist. La versione 1.2 riconosce entrambi i domini in tutti i passaggi, conserva i parametri firmati e aggiorna anche gli iframe aperti direttamente.

## Risultato della prova finale

| Film | Pagina → player → playlist | Tracce selezionate | Primi dati audio/video |
| --- | --- | --- | --- |
| Hubie Halloween | OK | 720p + italiano | HTTP 206, 2048 byte |
| Cars - Motori ruggenti | OK | 720p + italiano | HTTP 206, 2048 byte |
| Un weekend da bamboccioni | OK | 720p + italiano | HTTP 206, 2048 byte |

URL verificati:

- https://streamingcommunityz.day/it/watch/2305
- https://streamingcommunityz.day/it/watch/778
- https://streamingcommunityz.day/it/watch/1979

È stato eseguito il resolver Kotlin realmente compilato dall'app. La selezione delle tracce usa lo stesso selettore del servizio Android e yt-dlp `2025.11.12`, estratto dall'APK e verificato identico byte per byte a quello della nuova build. La simulazione usa `download=False`: nessun download completo viene avviato.

Per ciascun film sono state lette le playlist delle due tracce, le rispettive chiavi pubbliche HLS AES-128 di 16 byte e soltanto i primi 1.024 byte di ogni primo segmento. La decifratura di questi piccoli blocchi è avvenuta in memoria per verificarne le intestazioni MPEG-TS; nessun segmento o film è stato salvato. Il server dichiara `text/html` anche per i segmenti binari: la verifica riconosce i dati dal contenuto, senza basarsi solo sul Content-Type.

## Build

- JDK 17, SDK 35, Gradle 8.11.1.
- `testDebugUnitTest assembleDebug`: riuscito.
- 10 test superati, zero errori o fallimenti.
- Package `com.ronyxdumb.ytdlp`, versionName `1.2`, versionCode `3`.
- Firma APK v2 verificata.
- SHA-256 APK: `c64e821a65a31ad8f2dea0795808ed2e65d0f5e43cc67271b55b17d8578ef2df`.

## Installazione e limiti della verifica

Disinstalla la versione 1.1 prima di installare la 1.2: la firma di sviluppo è diversa da quella dell'APK precedente recuperato.

La prova del protocollo è stata eseguita su Linux/JVM. Non è stata eseguita su dispositivo o emulatore Android. Dimostra che, al momento del controllo, i tre flussi sono risolvibili, selezionabili e accessibili anche nei dati audio/video iniziali; non verifica un trasferimento completo, l'unione finale con FFmpeg, la riproduzione del risultato o il comportamento in background sul telefono. Le playlist e i token sono temporanei e vengono risolti di nuovo a ogni richiesta.

I dettagli senza token temporanei sono in `verification.json`.
