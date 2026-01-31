# Subtitle Translator for Kodi

Automatisk översättning av inbäddade undertexter när ingen undertext finns tillgänglig på ditt språk.

## Funktioner

- 🎬 **Automatisk detektering** - Upptäcker när undertext saknas på ditt föredragna språk
- 📥 **Extrahera inbäddade undertexter** - Använder FFmpeg för att extrahera SRT, ASS, SSA
- 🌐 **Flera översättningstjänster**:
  - DeepL (Pro och Free) - Bäst kvalitet
  - LibreTranslate - Gratis och öppen källkod
  - MyMemory - Gratis med begränsningar
  - Google Cloud Translation - Kräver API-nyckel
  - Microsoft Azure Translator - Kräver API-nyckel
  - Lingva - Gratis Google Translate-frontend
- 💾 **Caching** - Sparar översatta undertexter för snabb återanvändning
- ⚙️ **Konfigurerbart** - Välj språk, tjänster, format och mycket mer

## Installation

### Manuell installation

1. Ladda ner eller klona detta repository
2. Skapa en ZIP-fil av mappen `service.subtitletranslator`
3. I Kodi: Inställningar → Add-ons → Installera från ZIP-fil
4. Välj ZIP-filen

### Krav

- Kodi 19 (Matrix) eller senare
- FFmpeg installerat på systemet (för extraktion av inbäddade undertexter)
- Internetanslutning för översättning

## Konfiguration

Gå till Inställningar → Add-ons → Subtitle Translator → Konfigurera

### Allmänt
- **Aktivera tillägg** - Slå på/av tillägget
- **Automatisk översättning** - Översätt automatiskt när undertext saknas
- **Visa notifikation** - Visa meddelande under översättning
- **Fråga innan översättning** - Bekräfta innan översättning startar

### Språk
- **Målspråk** - Språket du vill ha undertexterna på (standard: Svenska)
- **Källspråk** - Språket att översätta från (standard: Engelska)

### Översättningstjänster

#### LibreTranslate (Gratis)
Standard och rekommenderat för de flesta. Använder publika instanser.

#### DeepL (Bäst kvalitet)
1. Skapa konto på [deepl.com](https://www.deepl.com/)
2. Kopiera din API-nyckel
3. Klistra in i inställningarna

#### MyMemory (Gratis)
Fungerar utan konfiguration men har dagliga begränsningar.

#### Google Cloud Translation
1. Skapa projekt i [Google Cloud Console](https://console.cloud.google.com/)
2. Aktivera Translation API
3. Skapa API-nyckel

#### Microsoft Translator
1. Skapa resurs i [Azure Portal](https://portal.azure.com/)
2. Kopiera API-nyckel och region

### Undertexter
- **Utdataformat** - SRT, ASS eller WebVTT
- **Cachelagra översättningar** - Spara för återanvändning
- **Spara bredvid video** - Lägg undertexten i samma mapp som videon

### Avancerat
- **FFmpeg-sökväg** - Ange om auto-detect inte hittar FFmpeg
- **Batch-storlek** - Antal rader per översättningsbegäran
- **Timeout** - Sekunder innan begäran avbryts

## Språkkoder

| Kod | Språk |
|-----|-------|
| sv | Svenska |
| en | Engelska |
| no | Norska |
| da | Danska |
| fi | Finska |
| de | Tyska |
| fr | Franska |
| es | Spanska |
| it | Italienska |
| nl | Nederländska |
| pl | Polska |
| pt | Portugisiska |
| ru | Ryska |
| ja | Japanska |
| zh | Kinesiska |
| ko | Koreanska |

## Felsökning

### "No embedded subtitles found"
- Videon innehåller inga inbäddade undertexter
- Testa att ladda ner extern undertext istället

### "Translation failed"
- Kontrollera internetanslutningen
- Verifiera API-nyckel om du använder betaltjänst
- Prova en annan översättningstjänst

### FFmpeg hittades inte
- Installera FFmpeg: `brew install ffmpeg` (macOS) eller `apt install ffmpeg` (Linux)
- Eller ange sökvägen manuellt i Avancerade inställningar

## Licens

MIT License

## Bidra

Pull requests välkomnas! Se [CONTRIBUTING.md](CONTRIBUTING.md) för riktlinjer.

## Tack till

- [FFmpeg](https://ffmpeg.org/) för undertextextraktion
- [DeepL](https://www.deepl.com/) för fantastisk översättningskvalitet
- [LibreTranslate](https://libretranslate.com/) för gratis och öppen översättning
