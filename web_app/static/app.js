const STORAGE_KEY = "minime.chat.rooms.v3";
const LEGACY_STORAGE_KEYS = ["minime.chat.rooms.v1", "minime.chat.rooms.v2"];
const MAX_API_MESSAGES = 6;

const state = {
  rooms: [],
  activeRoomId: null,
  isSending: false,
  modelReady: false,
};

const els = {
  sidebar: document.getElementById("sidebar"),
  sidebarToggle: document.getElementById("sidebarToggle"),
  newChatButton: document.getElementById("newChatButton"),
  chatList: document.getElementById("chatList"),
  messages: document.getElementById("messages"),
  composer: document.getElementById("composer"),
  input: document.getElementById("messageInput"),
  sendButton: document.getElementById("sendButton"),
  roomTitle: document.getElementById("roomTitle"),
  modelStatus: document.getElementById("modelStatus"),
  statusPill: document.getElementById("statusPill"),
};

function createId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function defaultRoom() {
  return {
    id: createId(),
    title: "New Chat",
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
}

function loadRooms() {
  for (const key of LEGACY_STORAGE_KEYS) {
    localStorage.removeItem(key);
  }

  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    state.rooms = Array.isArray(parsed) ? parsed : [];
  } catch {
    state.rooms = [];
  }

  if (state.rooms.length === 0) {
    state.rooms = [defaultRoom()];
  }
  state.activeRoomId = state.rooms[0].id;
}

function saveRooms() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.rooms));
}

function activeRoom() {
  return state.rooms.find((room) => room.id === state.activeRoomId) || state.rooms[0];
}

function titleFromMessage(text) {
  const normalized = text.replace(/\s+/g, " ").trim();
  return normalized.length > 34 ? `${normalized.slice(0, 34)}...` : normalized || "New Chat";
}

function cleanAssistantText(text) {
  return text
    .replace(/\s*\[(?:เศร้า|ขำ|โกรธ|ดีใจ|อบอุ่น|ขอร้อง|มีความสุข|ตกใจ|สงสัย|เบื่อ|ให้กำลังใจ|มั่นใจ)\]/g, "")
    .replace(/\s*\[[^\]\r\n]{1,20}\]/g, "")
    .replace(/(\S{1,12})(?:\s+\1){3,}/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .trimStart();
}

function apiMessages(messages) {
  return messages
    .filter((message) => !message.pending && !message.flagged)
    .map(({ role, content, flagged }) => ({ role, content, flagged: Boolean(flagged) }))
    .filter((message) => message.content && message.content.trim())
    .slice(-MAX_API_MESSAGES);
}

function renderRooms() {
  els.chatList.innerHTML = "";
  const sortedRooms = [...state.rooms].sort((a, b) => b.updatedAt - a.updatedAt);

  for (const room of sortedRooms) {
    const row = document.createElement("div");
    row.className = "chat-row";

    const select = document.createElement("button");
    select.type = "button";
    select.className = `chat-select ${room.id === state.activeRoomId ? "active" : ""}`;
    select.textContent = room.title;
    select.title = room.title;
    select.addEventListener("click", () => {
      if (state.isSending) return;
      state.activeRoomId = room.id;
      els.sidebar.classList.remove("open");
      render();
    });

    const del = document.createElement("button");
    del.type = "button";
    del.className = "chat-delete";
    del.textContent = "×";
    del.title = "Delete chat";
    del.addEventListener("click", () => deleteRoom(room.id));

    row.append(select, del);
    els.chatList.appendChild(row);
  }
}

function renderMessages() {
  const room = activeRoom();
  els.roomTitle.textContent = room.title;
  els.messages.innerHTML = "";

  if (room.messages.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <h2>เริ่มคุยกับ MiniMe</h2>
      <p>พิมพ์ข้อความเพื่อทดสอบโมเดล LoRA ภาษาไทย</p>
    `;
    els.messages.appendChild(empty);
    return;
  }

  for (const message of room.messages) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${message.role}`;

    const bubble = document.createElement("div");
    bubble.className = `bubble ${message.pending ? "pending" : ""}`;
    bubble.textContent = message.role === "assistant" ? cleanAssistantText(message.content || "") : message.content || "";

    wrapper.appendChild(bubble);
    els.messages.appendChild(wrapper);
  }

  requestAnimationFrame(() => {
    els.messages.scrollTop = els.messages.scrollHeight;
  });
}

function render() {
  renderRooms();
  renderMessages();
  els.sendButton.disabled = state.isSending || !state.modelReady;
}

function newChat() {
  if (state.isSending) return;
  const room = defaultRoom();
  state.rooms.unshift(room);
  state.activeRoomId = room.id;
  saveRooms();
  render();
  els.input.focus();
}

function deleteRoom(roomId) {
  if (state.isSending) return;
  state.rooms = state.rooms.filter((room) => room.id !== roomId);
  if (state.rooms.length === 0) {
    state.rooms = [defaultRoom()];
  }
  if (!state.rooms.some((room) => room.id === state.activeRoomId)) {
    state.activeRoomId = state.rooms[0].id;
  }
  saveRooms();
  render();
}

function setModelStatus(status, error) {
  state.modelReady = status === "ready";
  els.statusPill.className = `status-pill ${state.modelReady ? "ready" : status === "error" ? "error" : ""}`;
  els.statusPill.textContent = state.modelReady ? "Ready" : status === "error" ? "Error" : "Loading";
  els.modelStatus.textContent = state.modelReady
    ? "Model loaded"
    : status === "error"
      ? error || "Model failed to load"
      : "Loading model...";
  render();
}

async function pollHealth() {
  try {
    const response = await fetch("/health");
    const data = await response.json();
    setModelStatus(data.status, data.error);
    if (data.status !== "ready" && data.status !== "error") {
      setTimeout(pollHealth, 1600);
    }
  } catch {
    setModelStatus("error", "Server is not reachable");
  }
}

function sseLines(buffer) {
  const parts = buffer.split("\n\n");
  return {
    events: parts.slice(0, -1),
    rest: parts.at(-1) || "",
  };
}

function parseSse(chunk) {
  const event = { event: "message", data: "" };
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) event.event = line.slice(6).trim();
    if (line.startsWith("data:")) event.data += line.slice(5).trim();
  }
  try {
    event.data = JSON.parse(event.data || "{}");
  } catch {
    event.data = {};
  }
  return event;
}

async function sendMessage(text) {
  const room = activeRoom();
  if (!room || state.isSending || !state.modelReady) return;

  const firstUserMessage = room.messages.length === 0;
  room.messages.push({ role: "user", content: text });
  if (firstUserMessage) room.title = titleFromMessage(text);

  const assistantMessage = { role: "assistant", content: "", pending: true };
  room.messages.push(assistantMessage);
  room.updatedAt = Date.now();
  state.isSending = true;
  saveRooms();
  render();

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: apiMessages(room.messages),
        max_new_tokens: 24,
        temperature: 0,
        top_p: 1,
      }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`Request failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = sseLines(buffer);
      buffer = parsed.rest;

      for (const raw of parsed.events) {
        const sse = parseSse(raw);
        if (sse.event === "token") {
          assistantMessage.content += sse.data.text || "";
          assistantMessage.content = cleanAssistantText(assistantMessage.content);
          renderMessages();
        }
        if (sse.event === "error") {
          assistantMessage.content += `\n[${sse.data.message || "Generation error"}]`;
        }
        if (sse.event === "done") {
          assistantMessage.flagged = Boolean(sse.data.flagged);
          assistantMessage.pending = false;
        }
      }
    }
  } catch (error) {
    assistantMessage.content = `เกิดข้อผิดพลาด: ${error.message}`;
  } finally {
    assistantMessage.pending = false;
    room.updatedAt = Date.now();
    state.isSending = false;
    saveRooms();
    render();
    els.input.focus();
  }
}

function resizeInput() {
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 180)}px`;
}

els.newChatButton.addEventListener("click", newChat);
els.sidebarToggle.addEventListener("click", () => els.sidebar.classList.toggle("open"));
els.input.addEventListener("input", resizeInput);
els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    els.composer.requestSubmit();
  }
});

els.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = els.input.value.trim();
  if (!text) return;
  els.input.value = "";
  resizeInput();
  sendMessage(text);
});

loadRooms();
render();
pollHealth();
