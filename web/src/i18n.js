// Ikki tilli interfeys (o'zbek / ingliz). Foydalanuvchi tanlovi localStorage'da
// saqlanadi va sahifa qayta ochilganda tiklanadi.

export const LANGS = ['uz', 'en']

export const translations = {
  uz: {
    htmlLang: 'uz',
    title: "EUY-HTR — Eski o'zbek yozuvini tanib olish",
    tagline: "Eski o'zbek yozuvini tanib olish",
    langLabel: "O'z",
    langTitle: "O'zbekcha",
    dropTitle: "Tarixiy hujjat rasmini shu yerga tashlang yoki tanlash uchun bosing",
    dropHint: "JPG, PNG, TIFF, BMP, WEBP — bir nechta rasm mumkin",
    remove: "O'chirish",
    recognize: "Tanib olish",
    sending: "Yuborilmoqda...",
    clear: "Tozalash",
    statusPending: "Navbatda...",
    statusProcessing: "Ishlanmoqda...",
    statusDone: "Tayyor",
    statusError: "Xatolik",
    image: "Rasm",
    line: "satr",
    processingNote: "Server hujjatni qayta ishlamoqda. Bu sahifani yopmang.",
    errorPrefix: "Ishlovda xatolik:",
    retry: "Qaytadan",
    resultTitle: "Tanib olingan matn",
    imagesUnit: "rasm",
    linesUnit: "satr",
    copy: "Nusxa olish",
    newDoc: "Yangi hujjat",
    hint:
      "Eslatma: yuklab olinadigan fayllar serverdagi natija matnidan tayyorlanadi. " +
      "Yuqorida tahrirlangan o'zgartirishlar faylga kirmaydi.",
    detectedLines: "Aniqlangan satrlar",
    footer: "lokal server",
    imageAlt: "Rasm",
  },
  en: {
    htmlLang: 'en',
    title: "EUY-HTR — Old Uzbek handwritten text recognition",
    tagline: "Old Uzbek handwritten text recognition",
    langLabel: "EN",
    langTitle: "English",
    dropTitle: "Drop a historical document image here, or click to choose",
    dropHint: "JPG, PNG, TIFF, BMP, WEBP — multiple images allowed",
    remove: "Remove",
    recognize: "Recognize",
    sending: "Sending...",
    clear: "Clear",
    statusPending: "Queued...",
    statusProcessing: "Processing...",
    statusDone: "Done",
    statusError: "Error",
    image: "Image",
    line: "line",
    processingNote: "The server is processing the document. Do not close this page.",
    errorPrefix: "Processing error:",
    retry: "Try again",
    resultTitle: "Recognized text",
    imagesUnit: "images",
    linesUnit: "lines",
    copy: "Copy",
    newDoc: "New document",
    hint:
      "Note: downloaded files are generated from the result text on the server. " +
      "Edits made above are not included in the files.",
    detectedLines: "Detected lines",
    footer: "local server",
    imageAlt: "Image",
  },
}

const STORAGE_KEY = 'euyhtr_lang'

export function getInitialLang() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && LANGS.includes(saved)) return saved
  } catch {
    /* localStorage mavjud emas */
  }
  return 'uz'
}

export function saveLang(lang) {
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    /* localStorage mavjud emas */
  }
}
