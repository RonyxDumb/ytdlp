# YtDlp Windows

**By Francesco Pio Pipino** · Versione 1.1.0 · Windows 10/11 x64

## Uso

1. Scarica `YtDlp-Windows-x64.zip` dalle release GitHub di `RonyxDumb/ytdlp`.
2. Estrai lo ZIP in una cartella scrivibile, per esempio sul Desktop. Avvia `YtDlp.exe`.
3. Incolla un indirizzo HTTP/HTTPS, scegli **Formato del download** e premi **Scarica video** / **Scarica audio**, oppure Invio.
4. Sotto l'indirizzo trovi la barra, la velocità e il tempo stimato. **Annulla** interrompe anche i processi di download e unione.
5. Il risultato viene salvato in `Download/YtDlp`, oppure nella cartella scelta con **Cambia…**.

Un download per volta, nessuna playlist. Il completamento viene indicato solo dopo che yt-dlp ha restituito il percorso del file finale. Durante analisi e unione la barra è animata; per le tracce con dimensione nota indica i byte ricevuti. Con tracce video e audio separate la percentuale può ripartire per la traccia successiva. Non vengono sovrascritti file completati; i parziali vengono mantenuti per ritentare.

## Formati

| Scelta | Risultato |
| --- | --- |
| MP4 | Video e audio; preferenza H.264/AAC, conversione in MP4 se necessaria |
| MKV | Video e audio, cambio del contenitore senza ricodifica |
| WebM | Video e audio; conversione in WebM se necessaria |
| Automatico | Formato scelto da yt-dlp, senza conversione forzata |
| MP3 / M4A / Opus / OGG | Solo audio, con conversione se necessaria; OGG usa Vorbis |
| WAV | Solo audio PCM non compresso, con file più grandi |
| FLAC | Solo audio con compressione senza perdita |

L'ultima scelta viene ricordata. La qualità dipende dalla sorgente: convertirla in WAV o FLAC non recupera informazioni già perse. La conversione video può richiedere tempo; il formato MP4 non impone la ricodifica se il file è già MP4 e non garantisce un codec specifico quando il sito fornisce solo altri codec.

I nomi includono il formato scelto, per esempio `Titolo [id] [mp3].mp3`, così più formati dello stesso video possono coesistere. I temporanei vengono separati in `.ytdlp-tmp/<formato>` e riutilizzati in caso di nuovo tentativo.

## Strumenti al primo avvio

Il primo download richiede Internet anche per preparare i componenti nella cartella `%LOCALAPPDATA%/YtDlp/tools`:

- `yt-dlp.exe` da `yt-dlp/yt-dlp`;
- FFmpeg e FFprobe con le DLL dalla build Windows x64 di `yt-dlp/FFmpeg-Builds`;
- `deno.exe` da `denoland/deno`, per il runtime JavaScript usato dagli estrattori YouTube.

Ogni pacchetto viene confrontato con dimensione e SHA-256 dichiarati da GitHub. Un file incompleto o con verifica fallita non viene installato. L'app riutilizza poi gli strumenti locali senza riscaricarli a ogni download. **Impostazioni → Aggiorna motore yt-dlp e strumenti** cerca nuove versioni ufficiali; questo comando è separato dall'aggiornamento dell'app.

Il resolver di StreamingCommunity/VixCloud deriva dall'app Android: legge la configurazione pubblica a ogni richiesta, senza eseguire il JavaScript del sito e senza incorporare indirizzi temporanei. I cambiamenti dei siti possono richiedere nuove correzioni. La preferenza per l'audio italiano resta attiva anche scegliendo solo audio. Login, DRM e protezioni anti-bot non sono gestiti dall'interfaccia.

## Aggiornamento dell'app

La verifica GitHub avviene all'apertura senza bloccare l'interfaccia e con il pulsante **Verifica aggiornamenti**. Sono considerate solo release stabili con tag `windows-vX.Y.Z` e allegato `YtDlp-Windows-x64.zip`: le release Android vengono ignorate e le versioni sono confrontate numericamente.

Quando è disponibile una nuova versione appare **Aggiorna app**. Dopo la conferma, l'app scarica e verifica lo ZIP, prepara il nuovo eseguibile, attende la chiusura del processo attuale e lo sostituisce. `YtDlp.exe.previous.exe` conserva il file precedente. Un errore durante la sostituzione ripristina la copia precedente; i dettagli sono in `%LOCALAPPDATA%/YtDlp/update-error.txt`. La cartella dell'app deve essere scrivibile.

Il repository `RonyxDumb/ytdlp` è pubblico e non serve alcun token per gli aggiornamenti. Un token facoltativo può essere inserito in **Impostazioni** per un eventuale repository privato o per aumentare il limite delle richieste API: usa un fine-grained token con accesso solo a questo repository e `Contents: Read-only`. L'app usa l'API anche per gli allegati privati e non inoltra il token ai server CDN. Il token è conservato come credenziale Windows, non nel file delle preferenze. Per rimuoverlo, svuota il campo e salva.

## Compila dal codice

Installa Python **3.13 x64** con Tcl/Tk e l'opzione per aggiungerlo al PATH. Da Windows fai doppio clic su `windows/build.bat`. Oppure:

```powershell
cd windows
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Risultati in `windows/dist/`: `YtDlp.exe`, `YtDlp-Windows-x64.zip` e checksum. Il programma finale include Python/Tk; l'utente non deve installarli. Gli strumenti di download vengono preparati separatamente al primo utilizzo.

Per lavorare ai sorgenti senza compilare: `cd windows` e `python main.py`. Solo il pacchetto compilato può sostituire automaticamente il proprio eseguibile. Test: `python -m unittest discover -s tests -v`. Su Windows, `python main.py --smoke-test` verifica l'interfaccia e il selettore senza richieste di rete. `YTDLP_INTEGRATION=1` abilita anche le conversioni di tutti i formati con il vero yt-dlp e FFmpeg, usando un breve file servito su localhost. Le prove verificano codec e tracce, conversione WebM → MP4, tracce DASH separate → WebM, ripetizione del download e conservazione del video quando si scarica anche l'audio. Le prove dei formati sono eseguibili anche su Linux con `yt-dlp`, `ffmpeg` e `ffprobe` nel PATH.

Il workflow `.github/workflows/windows.yml` esegue test su Windows, compila e prova l'eseguibile, carica gli artefatti e pubblica le versioni nuove. Per una release cambia `VERSION` in `ytdlp_windows/__init__.py` e `RELEASE_NOTES.md`. Non incorporare token personali nella build.
