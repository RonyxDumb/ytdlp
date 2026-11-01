# YtDlp Android

App nativa Android in italiano, con Material 3 / Material You, colori dinamici su Android 12+, tema chiaro/scuro e barre di sistema trasparenti. Android 10 o successivo. ABI incluse: arm64-v8a, armeabi-v7a, x86_64.

## Installa
Compila il progetto seguendo le istruzioni sotto, poi apri `output/YtDlp.apk` sul telefono e autorizza l'installazione da questa fonte. Il repository contiene i sorgenti; gli APK generati restano esclusi da Git. L'APK è una build debug firmata, installabile direttamente. La versione 1.2 ha una firma di sviluppo diversa dalla 1.1: disinstalla la vecchia app prima di installarla. Non è una release destinata al Play Store.

## Novità 1.2
- Corretto il blocco dei link StreamingCommunity che incorporano il player `vixcloud.cc`: la versione 1.1 riconosceva esclusivamente `vixcloud.co`.
- Il dominio attuale è riconosciuto nella pagina iframe, nei link diretti di embed e nella configurazione della playlist; resta supportato il precedente `.co`.
- Conservati i parametri temporanei del player e la preferenza per l'audio italiano.
- Richiesta aggiornata anche quando si incolla direttamente una pagina `/it/iframe/`, per non riutilizzare un embed scaduto.
- Dieci test del resolver, inclusi entrambi i domini e il rifiuto di domini simili ma estranei.

La risoluzione segue pagina → iframe → playlist HLS, senza eseguire il JavaScript pubblicitario del sito. I token vengono letti dalla configurazione pubblica del player a ogni richiesta; nessun indirizzo temporaneo è incorporato nell'APK. Il download premium del sito non viene utilizzato.

## Usa
Incolla un link HTTP/HTTPS e premi **Scarica video**. Puoi anche condividere un link verso YtDlp da un'altra app. Un video per volta, nessuna playlist. Il servizio mantiene il download attivo e mostra una notifica con il pulsante Annulla. Il risultato appare in `Download/YtDlp/`, tramite MediaStore, senza permessi di accesso completo alla memoria.

Il motore scrive temporaneamente nella memoria privata dell'app e copia poi il risultato nei Download: serve spazio per il video e la copia finale. I temporanei vengono rimossi al termine. Per due video con lo stesso nome Android gestisce l'eventuale conflitto nella raccolta Download.

**Aggiorna yt-dlp** scarica l'ultima versione stabile del motore. Usalo se un sito smette di funzionare. I siti supportati dipendono da yt-dlp: download privati, DRM, richieste di login e controlli anti-bot non sono gestiti dall'interfaccia. Non è garantito che ogni link YouTube o di altri siti funzioni. La preferenza dei codec migliora la compatibilità, ma non è una conversione forzata: se il sito offre solo altri codec, il fallback può produrre un file che la Galleria non legge. Scarica solo contenuti per cui hai il permesso.

## Compila su Windows
1. Installa e avvia Docker Desktop con container Linux.
2. Clona il repository con `git clone https://github.com/RonyxDumb/ytdlp-android.git`, oppure scarica ed estrai lo ZIP dei sorgenti.
3. Entra nella cartella `android` e fai doppio clic su `docker_build.bat`.
4. Attendi: la prima build scarica SDK, Gradle e dipendenze; serve Internet.
5. L'APK viene creato in `output/YtDlp.apk` e la cartella si apre automaticamente.

Non occorre installare Java, Android Studio o l'SDK su Windows. In PowerShell puoi eseguire `./docker_build.bat`. Da Linux/macOS: `docker build -t ytdlp-android-builder .` e poi `docker run --rm -v "$PWD:/src" ytdlp-android-builder`.

Per Android Studio: apri la cartella `android` e sincronizza Gradle. JDK 17, SDK 35, Gradle 8.11.1. La build Docker usa un progetto temporaneo interno al container e scrive solo l'APK nella cartella output.

## Dipendenze e licenze
- youtubedl-android / FFmpeg wrapper 0.18.1: https://github.com/yausername/youtubedl-android (licenza MIT allegata).
- yt-dlp: https://github.com/yt-dlp/yt-dlp (Unlicense; componenti e pacchetti precompilati possono avere licenze aggiuntive).
- FFmpeg: https://ffmpeg.org/legal.html (componenti distribuiti dalla dipendenza Android).
- Material Components e AndroidX: Apache-2.0.

## Verifica

Compilazione: `./gradlew testDebugUnitTest assembleDebug`, JDK 17, SDK 35 e Gradle 8.11.1. Dieci test superati; APK 1.2, versionCode 3, firma v2 verificata.

Il resoconto della prova dei tre link segnalati è in `VERIFICA.md` e `verification.json`. La prova usa il resolver Kotlin compilato e lo stesso yt-dlp incluso nell'APK: verifica le playlist, la selezione delle tracce e una lettura limitata dei segmenti. Non scarica i film completi. La prova del protocollo è eseguita su Linux/JVM, senza dispositivo o emulatore Android; installazione sul telefono, trasferimento completo, unione finale e comportamento in background restano da provare sul dispositivo.

Il pulsante **Aggiorna yt-dlp** aggiorna il motore generale. Le correzioni del resolver StreamingCommunity richiedono un aggiornamento dell'APK.
