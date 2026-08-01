const itemsEl = document.getElementById("items");
const brandEl = document.getElementById("brand");
const monthEl = document.getElementById("month");
const yearEl = document.getElementById("year");
const statusEl = document.getElementById("status");
const bannerEl = document.getElementById("banner");
const generateBtn = document.getElementById("generate");

const MONTHS_TR = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

let itemCounter = 0;
const itemState = new Map(); // id -> { kind: "image"|"video"|null, files: File[] }

function showBanner(kind, message) {
  bannerEl.hidden = false;
  bannerEl.className = `banner ${kind}`;
  bannerEl.textContent = message;
}

function hideBanner() {
  bannerEl.hidden = true;
}

function initDefaults() {
  const now = new Date();
  monthEl.value = MONTHS_TR[now.getMonth()];
  yearEl.value = now.getFullYear();
}

async function loadBrands() {
  try {
    const res = await fetch("/api/brands");
    if (!res.ok) throw new Error(`Sunucu hatası (${res.status})`);
    const brands = await res.json();
    brandEl.innerHTML = brands
      .map((b) => `<option value="${b.id}">${b.display_name}</option>`)
      .join("");
  } catch (e) {
    showBanner("error", `Markalar yüklenemedi: ${e.message}. Sunucu çalışıyor mu?`);
  }
}

function addItem() {
  itemCounter += 1;
  const id = itemCounter;
  itemState.set(id, { kind: null, files: [] });

  const card = document.createElement("div");
  card.className = "item-card";
  card.dataset.id = id;
  card.innerHTML = `
    <h3>İçerik ${id} <button type="button" data-remove>Kaldır</button></h3>
    <div class="dropzone" data-dropzone>
      <div data-dz-content>1 video veya en fazla 2 görsel sürükleyin ya da tıklayıp seçin</div>
      <input type="file" accept="image/*,video/*" multiple hidden data-file-input />
    </div>
    <div class="caption-row">
      <textarea placeholder="Açıklama + hashtag... (veya AI ile oluştur)" data-caption></textarea>
      <button type="button" class="ai-btn" data-ai-btn>✨ AI ile Oluştur</button>
    </div>
  `;
  itemsEl.appendChild(card);

  const dropzone = card.querySelector("[data-dropzone]");
  const fileInput = card.querySelector("[data-file-input]");
  const aiBtn = card.querySelector("[data-ai-btn]");

  dropzone.addEventListener("click", (e) => {
    if (dropzone.classList.contains("filled")) return; // "Değiştir"/"+" kendi input'unu tetikler
    fileInput.click();
  });
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    handleFiles(id, dropzone, e.dataTransfer.files);
  });
  fileInput.addEventListener("change", () => {
    handleFiles(id, dropzone, fileInput.files);
  });

  card.querySelector("[data-remove]").addEventListener("click", () => {
    itemState.delete(id);
    card.remove();
  });

  aiBtn.addEventListener("click", () => generateAiCaption(id, card));
}

function handleFiles(id, dropzone, fileList) {
  const files = [...fileList];
  if (!files.length) return;

  const videos = files.filter((f) => f.type.startsWith("video/"));
  const images = files.filter((f) => f.type.startsWith("image/"));

  let state;
  if (videos.length) {
    state = { kind: "video", files: [videos[0]] };
  } else if (images.length) {
    state = { kind: "image", files: images.slice(0, 2) };
  } else {
    showBanner("error", "Desteklenmeyen dosya türü. Görsel veya video seçin.");
    return;
  }

  itemState.set(id, state);
  renderPreview(dropzone, state);
}

function renderPreview(dropzone, state) {
  const urls = state.files.map((f) => URL.createObjectURL(f));
  dropzone.classList.add("filled");
  const canAddMore = state.kind === "image" && state.files.length < 2;

  if (state.kind === "video") {
    dropzone.innerHTML = `
      <div class="preview-row"><video src="${urls[0]}" controls muted></video></div>
      <span class="change-link" data-change>Değiştir</span>
    `;
  } else {
    const imgs = urls.map((u) => `<img src="${u}" alt="" />`).join("");
    dropzone.innerHTML = `
      <div class="preview-row">${imgs}</div>
      <span class="change-link" data-change>Değiştir</span>${canAddMore ? '<span class="change-link" data-add>+ Görsel ekle</span>' : ""}
    `;
  }

  const cardId = dropzone.closest(".item-card").dataset.id;

  const changeInput = document.createElement("input");
  changeInput.type = "file";
  changeInput.accept = "image/*,video/*";
  changeInput.multiple = true;
  changeInput.hidden = true;
  dropzone.appendChild(changeInput);
  changeInput.addEventListener("change", () => handleFiles(Number(cardId), dropzone, changeInput.files));
  dropzone.querySelector("[data-change]").addEventListener("click", (e) => {
    e.stopPropagation();
    changeInput.click();
  });

  if (canAddMore) {
    const addInput = document.createElement("input");
    addInput.type = "file";
    addInput.accept = "image/*";
    addInput.multiple = true;
    addInput.hidden = true;
    dropzone.appendChild(addInput);
    addInput.addEventListener("change", () => addMoreImages(Number(cardId), dropzone, addInput.files));
    dropzone.querySelector("[data-add]").addEventListener("click", (e) => {
      e.stopPropagation();
      addInput.click();
    });
  }
}

function addMoreImages(id, dropzone, fileList) {
  const state = itemState.get(id);
  if (!state || state.kind !== "image") return;
  const newImages = [...fileList].filter((f) => f.type.startsWith("image/"));
  if (!newImages.length) return;
  const combined = [...state.files, ...newImages].slice(0, 2);
  const newState = { kind: "image", files: combined };
  itemState.set(id, newState);
  renderPreview(dropzone, newState);
}

async function generateAiCaption(id, card) {
  const state = itemState.get(id);
  const captionEl = card.querySelector("[data-caption]");
  const aiBtn = card.querySelector("[data-ai-btn]");

  if (!state || !state.files.length) {
    showBanner("error", `İçerik ${id}: önce bir görsel veya video seçin.`);
    return;
  }
  if (!brandEl.value) {
    showBanner("error", "Önce bir marka seçin.");
    return;
  }

  aiBtn.disabled = true;
  aiBtn.textContent = "Üretiliyor...";
  hideBanner();

  try {
    const formData = new FormData();
    formData.append("brand", brandEl.value);
    formData.append("file", state.files[0]);

    const res = await fetch("/api/caption", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Sunucu hatası (${res.status})`);
    }
    const data = await res.json();
    captionEl.value = data.caption;
  } catch (e) {
    showBanner("error", `AI açıklama üretilemedi: ${e.message}`);
  } finally {
    aiBtn.disabled = false;
    aiBtn.textContent = "✨ AI ile Oluştur";
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function generate() {
  hideBanner();
  const cards = [...itemsEl.querySelectorAll(".item-card")];
  if (!cards.length) {
    showBanner("error", "En az bir içerik ekleyin.");
    return;
  }
  if (!brandEl.value) {
    showBanner("error", "Bir marka seçin.");
    return;
  }

  generateBtn.disabled = true;
  statusEl.textContent = "Sunum oluşturuluyor...";

  try {
    const formData = new FormData();
    formData.append("brand", brandEl.value);
    formData.append("month", monthEl.value);
    formData.append("year", yearEl.value);

    for (const card of cards) {
      const id = Number(card.dataset.id);
      const state = itemState.get(id);
      const caption = card.querySelector("[data-caption]").value;

      if (!state || !state.files.length) {
        throw new Error(`İçerik ${id}: bir görsel veya video seçmediniz.`);
      }

      formData.append("captions", caption);
      formData.append("kinds", state.kind);
      for (const file of state.files) {
        formData.append("files", file);
        formData.append("file_item_index", String(cards.indexOf(card)));
      }
    }

    const res = await fetch("/api/assemble", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Sunucu hatası (${res.status})`);
    }

    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition") || "";
    const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)"?/i);
    const filename = match ? decodeURIComponent(match[1]) : "sunum.pptx";

    downloadBlob(blob, filename);
    statusEl.textContent = "";
    showBanner("success", `Hazır — "${filename}" indirildi.`);
  } catch (e) {
    statusEl.textContent = "";
    showBanner("error", `Hata: ${e.message}`);
  } finally {
    generateBtn.disabled = false;
  }
}

document.getElementById("add-item").addEventListener("click", addItem);
generateBtn.addEventListener("click", () => {
  generate().catch((e) => showBanner("error", `Beklenmeyen hata: ${e.message}`));
});

initDefaults();
loadBrands();
addItem();
