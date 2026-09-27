"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent, KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Source = { title: string; url: string };
type Attachment = {
  id: string;
  name: string;
  type: string;
  size: number;
  dataUrl: string;
  textContent?: string;
};
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachments?: Attachment[];
  error?: boolean;
  sources?: Source[];
  webSearch?: boolean;
  provider?: string;
  model?: string;
  task?: string;
};
type Conversation = { id: string; title: string; created_at: string; updated_at: string };
type CatalogProvider = { id: string; name: string; configured: boolean; models: string[]; model_count_note?: string };
type ModelCatalog = { providers: CatalogProvider[]; free_model_count?: number };
type IconName =
  | "spark"
  | "plus"
  | "search"
  | "moon"
  | "sun"
  | "menu"
  | "panel"
  | "send"
  | "stop"
  | "image"
  | "file"
  | "camera"
  | "x"
  | "copy"
  | "edit"
  | "refresh"
  | "trash"
  | "chevron"
  | "check"
  | "shield"
  | "paperclip"
  | "arrow"
  | "dots"
  | "folder"
  | "message"
  | "zap";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const CONVERSATION_KEY = "silent_ai_conversation_id";
const THEME_KEY = "silent_ai_theme";
const MAX_FILE_SIZE = 20 * 1024 * 1024;
const MAX_TEXT_CHARS = 180_000;

const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (name) {
    case "spark": return <svg {...common}><path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2Z"/><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z"/></svg>;
    case "plus": return <svg {...common}><path d="M12 5v14M5 12h14"/></svg>;
    case "search": return <svg {...common}><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>;
    case "moon": return <svg {...common}><path d="M20.5 14.4A8.6 8.6 0 0 1 9.6 3.5 8.7 8.7 0 1 0 20.5 14.4Z"/></svg>;
    case "sun": return <svg {...common}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>;
    case "menu": return <svg {...common}><path d="M4 6h16M4 12h16M4 18h16"/></svg>;
    case "panel": return <svg {...common}><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M8 4v16"/></svg>;
    case "send": return <svg {...common}><path d="m4 4 16 8-16 8 3.5-8L4 4Z"/><path d="M7.5 12H20"/></svg>;
    case "stop": return <svg {...common}><rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none"/></svg>;
    case "image": return <svg {...common}><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="8.5" cy="9" r="1.5"/><path d="m4 17 5-5 3.5 3.5 2.5-2.5 5 5"/></svg>;
    case "file": return <svg {...common}><path d="M7 3h7l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M14 3v5h5M8 13h8M8 17h6"/></svg>;
    case "camera": return <svg {...common}><path d="M5 7h3l1.3-2h5.4L16 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z"/><circle cx="12" cy="13" r="3.5"/></svg>;
    case "x": return <svg {...common}><path d="m6 6 12 12M18 6 6 18"/></svg>;
    case "copy": return <svg {...common}><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>;
    case "edit": return <svg {...common}><path d="m4 16-.7 4.7L8 20l11-11-4-4L4 16Z"/><path d="m13.5 6.5 4 4"/></svg>;
    case "refresh": return <svg {...common}><path d="M20 11a8 8 0 0 0-14.9-4L3 10"/><path d="M3 5v5h5"/><path d="M4 13a8 8 0 0 0 14.9 4L21 14"/><path d="M21 19v-5h-5"/></svg>;
    case "trash": return <svg {...common}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 14h10l1-14M9 7V4h6v3"/></svg>;
    case "chevron": return <svg {...common}><path d="m8 10 4 4 4-4"/></svg>;
    case "check": return <svg {...common}><path d="m5 12 4 4L19 6"/></svg>;
    case "shield": return <svg {...common}><path d="M12 3 20 6v5c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3Z"/><path d="m9 12 2 2 4-4"/></svg>;
    case "paperclip": return <svg {...common}><path d="m21 11.5-8.7 8.7a5 5 0 0 1-7.1-7.1l9.2-9.2a3.5 3.5 0 0 1 5 5l-9.3 9.3a2 2 0 0 1-2.8-2.8l8.6-8.6"/></svg>;
    case "arrow": return <svg {...common}><path d="M5 12h14M13 6l6 6-6 6"/></svg>;
    case "dots": return <svg {...common}><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none"/></svg>;
    case "folder": return <svg {...common}><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg>;
    case "message": return <svg {...common}><path d="M5 5h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-4 3v-3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z"/></svg>;
    case "zap": return <svg {...common}><path d="m13 2-9 12h7l-1 8 9-12h-7l1-8Z"/></svg>;
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function isTextLike(file: File) {
  return file.type.startsWith("text/") || /\.(txt|md|markdown|json|csv|ts|tsx|js|jsx|py|java|cpp|c|h|css|html|xml|yaml|yml|sql|sh|ps1|env|log)$/i.test(file.name);
}

export default function Home() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [search, setSearch] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("auto");
  const [selectedModel, setSelectedModel] = useState("auto");
  const [activeEngine, setActiveEngine] = useState("Auto Brain");

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const noticeTimerRef = useRef<number | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const activeConversation = useMemo(() => conversations.find((item) => item.id === conversationId), [conversations, conversationId]);
  const filteredConversations = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return conversations;
    return conversations.filter((item) => item.title.toLowerCase().includes(query));
  }, [conversations, search]);

  const showNotice = useCallback((text: string) => {
    setNotice(text);
    if (noticeTimerRef.current) window.clearTimeout(noticeTimerRef.current);
    noticeTimerRef.current = window.setTimeout(() => setNotice(""), 2600);
  }, []);

  const scrollToBottom = useCallback((smooth = false) => {
    requestAnimationFrame(() => messagesEndRef.current?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "end" }));
  }, []);

  const applyTheme = useCallback((nextTheme: "dark" | "light") => {
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    document.body.dataset.theme = nextTheme;
    localStorage.setItem(THEME_KEY, nextTheme);
    document.documentElement.style.colorScheme = nextTheme;
  }, []);

  const toggleTheme = useCallback(() => {
    applyTheme(theme === "dark" ? "light" : "dark");
  }, [applyTheme, theme]);

  useEffect(() => {
    const savedTheme = localStorage.getItem(THEME_KEY);
    const initial = savedTheme === "light" ? "light" : "dark";
    setTheme(initial);
    document.documentElement.dataset.theme = initial;
    document.body.dataset.theme = initial;
    document.documentElement.style.colorScheme = initial;

    const init = async () => {
      try {
        await loadConversations();
        void loadModelCatalog();
        const saved = localStorage.getItem(CONVERSATION_KEY);
        if (saved) await loadConversation(saved);
      } catch (error) {
        console.error(error);
        setServerOnline(false);
      }
    };
    void init();
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.body.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 190)}px`;
  }, [message]);

  useEffect(() => {
    scrollToBottom(loading ? false : true);
  }, [messages, loading, scrollToBottom]);

  useEffect(() => {
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        void createNewConversation();
      }
      if (event.key === "Escape") {
        if (showCamera) closeCamera();
        else if (loading) stopGeneration();
        else setShowAttachMenu(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  useEffect(() => () => {
    abortControllerRef.current?.abort();
    stopCameraStream();
    if (noticeTimerRef.current) window.clearTimeout(noticeTimerRef.current);
  }, []);

  async function loadModelCatalog() {
    try {
      const response = await fetch(`${API_URL}/models`);
      if (!response.ok) return;
      const data = await response.json();
      setCatalog(data?.catalog || null);
    } catch {
      // Model catalog is optional; chat can still work through Auto Brain.
    }
  }

  async function loadConversations() {
    const response = await fetch(`${API_URL}/conversations`);
    if (!response.ok) throw new Error("تعذر تحميل المحادثات");
    const data = await response.json();
    setConversations(data?.conversations || []);
    setServerOnline(true);
  }

  async function loadConversation(id: string): Promise<boolean> {
    if (loading) return false;
    try {
      const response = await fetch(`${API_URL}/conversations/${id}`);
      if (!response.ok) {
        localStorage.removeItem(CONVERSATION_KEY);
        return false;
      }
      const data = await response.json();
      setConversationId(id);
      setMessages((data?.messages || []).map((item: { role?: string; content?: string }, index: number) => ({
        id: `${id}-${index}`,
        role: item.role === "user" ? "user" : "assistant",
        content: item.content || "",
      })));
      localStorage.setItem(CONVERSATION_KEY, id);
      setServerOnline(true);
      if (window.innerWidth < 980) setSidebarOpen(false);
      return true;
    } catch (error) {
      console.error(error);
      setServerOnline(false);
      return false;
    }
  }

  async function createNewConversation() {
    if (loading) return;
    setConversationId(null);
    setMessages([]);
    setMessage("");
    setAttachments([]);
    setActiveMenu(null);
    setShowAttachMenu(false);
    localStorage.removeItem(CONVERSATION_KEY);
    if (window.innerWidth < 980) setSidebarOpen(false);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  async function deleteConversation(id: string) {
    if (loading) return;
    if (!window.confirm("حذف المحادثة نهائيًا؟")) return;
    try {
      const response = await fetch(`${API_URL}/conversations/${id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("فشل حذف المحادثة");
      if (conversationId === id) await createNewConversation();
      await loadConversations();
      showNotice("تم حذف المحادثة");
    } catch (error) {
      console.error(error);
      showNotice("تعذر حذف المحادثة");
    }
  }

  async function fileToAttachment(file: File): Promise<Attachment | null> {
    if (file.size > MAX_FILE_SIZE) {
      showNotice(`${file.name} أكبر من 20MB`);
      return null;
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
    if (!dataUrl) return null;

    let textContent: string | undefined;
    if (isTextLike(file)) {
      try {
        textContent = (await file.text()).slice(0, MAX_TEXT_CHARS);
      } catch {
        textContent = undefined;
      }
    }

    return { id: uid(), name: file.name, type: file.type || "application/octet-stream", size: file.size, dataUrl, textContent };
  }

  async function addFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (!files.length) return;
    const next: Attachment[] = [];
    for (const file of files.slice(0, 6)) {
      const item = await fileToAttachment(file);
      if (item) next.push(item);
    }
    if (next.length) {
      setAttachments((current) => [...current, ...next].slice(0, 6));
      setShowAttachMenu(false);
      showNotice(`${next.length} ملف جاهز للإرسال`);
    }
  }

  function handleImageSelect(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    event.target.value = "";
    if (files) void addFiles(Array.from(files).filter((file) => file.type.startsWith("image/")));
  }

  function handleFileSelect(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    event.target.value = "";
    if (files) void addFiles(files);
  }

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    if (!loading) setDragActive(true);
  }

  function onDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    if (!loading) void addFiles(event.dataTransfer.files);
  }

  async function openCamera() {
    setShowAttachMenu(false);
    if (!navigator.mediaDevices?.getUserMedia) {
      showNotice("الكاميرا غير متاحة في هذا المتصفح");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false });
      streamRef.current = stream;
      setShowCamera(true);
      requestAnimationFrame(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play();
        }
      });
    } catch (error) {
      console.error(error);
      showNotice("اسمح للمتصفح باستخدام الكاميرا ثم جرّب تاني");
    }
  }

  function stopCameraStream() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function closeCamera() {
    stopCameraStream();
    setShowCamera(false);
  }

  function captureCamera() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return showNotice("الكاميرا لسه بتجهز");
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], `camera-${new Date().toISOString().replace(/[:.]/g, "-")}.jpg`, { type: "image/jpeg" });
      void addFiles([file]);
      closeCamera();
    }, "image/jpeg", 0.92);
  }

  function removeAttachment(id: string) {
    setAttachments((current) => current.filter((item) => item.id !== id));
  }

  function setSuggestion(text: string) {
    setMessage(text);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  async function copyText(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      window.setTimeout(() => setCopiedKey(null), 1500);
    } catch {
      showNotice("تعذر النسخ");
    }
  }

  function updateAssistant(content: string) {
    setMessages((current) => {
      const next = [...current];
      const last = next.length - 1;
      if (last >= 0 && next[last].role === "assistant") next[last] = { ...next[last], content, error: false };
      else next.push({ id: uid(), role: "assistant", content });
      return next;
    });
  }

  function updateAssistantMeta(meta: { webSearch?: boolean; sources?: Source[]; provider?: string; model?: string; task?: string }) {
    setMessages((current) => {
      const next = [...current];
      const last = next.length - 1;
      if (last < 0 || next[last].role !== "assistant") return current;
      next[last] = { ...next[last], webSearch: meta.webSearch ?? next[last].webSearch, sources: meta.sources ?? next[last].sources, provider: meta.provider ?? next[last].provider, model: meta.model ?? next[last].model, task: meta.task ?? next[last].task };
      return next;
    });
  }

  async function readSSEStream(response: Response, onEvent: (eventName: string, data: Record<string, unknown>) => void) {
    if (!response.body) throw new Error("المتصفح لا يدعم Streaming");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";
      for (const block of blocks) {
        let eventName = "message";
        let dataText = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) eventName = line.slice(6).trim();
          if (line.startsWith("data:")) dataText += line.slice(5).trim();
        }
        if (!dataText) continue;
        try { onEvent(eventName, JSON.parse(dataText)); } catch { /* ignore malformed chunks */ }
      }
    }
  }

  async function sendLegacyRequest(payload: Record<string, unknown>) {
    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: abortControllerRef.current?.signal,
    });
    if (!response.ok) {
      let detail = "حدث خطأ في الـBackend";
      try { detail = (await response.json())?.detail || detail; } catch {}
      throw new Error(detail);
    }
    const data = await response.json();
    if (data?.conversation_id) {
      setConversationId(data.conversation_id);
      localStorage.setItem(CONVERSATION_KEY, data.conversation_id);
    }
    updateAssistant(data?.reply || "");
    updateAssistantMeta({ provider: typeof data?.provider === "string" ? data.provider : undefined, model: typeof data?.model === "string" ? data.model : undefined, task: typeof data?.task === "string" ? data.task : undefined });
    if (typeof data?.provider === "string") setActiveEngine(`${data.provider}${data.model ? ` · ${data.model}` : ""}`);
  }

  async function sendMessage(customText?: string) {
    const text = (customText ?? message).trim();
    if ((!text && !attachments.length) || loading) return;
    const finalText = text || "حلل الملفات والصور المرفقة واذكر أهم ما تراه فيها.";
    const outgoingAttachments = [...attachments];
    const userMessage: Message = { id: uid(), role: "user", content: finalText, attachments: outgoingAttachments };
    const assistantId = uid();
    setMessages((current) => [...current, userMessage, { id: assistantId, role: "assistant", content: "" }]);
    setMessage("");
    setAttachments([]);
    setLoading(true);
    setShowAttachMenu(false);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const imageAttachment = outgoingAttachments.find((item) => item.type.startsWith("image/"));
    const textFiles = outgoingAttachments.filter((item) => item.textContent).map((item) => `\n\n--- ملف: ${item.name} ---\n${item.textContent}`).join("");
    const enrichedMessage = `${finalText}${textFiles}`.slice(0, MAX_TEXT_CHARS + 12_000);
    const payload = {
      message: enrichedMessage,
      conversation_id: conversationId,
      attachment: imageAttachment ? { name: imageAttachment.name, type: imageAttachment.type, data_url: imageAttachment.dataUrl } : null,
      attachments: outgoingAttachments.map((item) => ({ name: item.name, type: item.type, size: item.size, data_url: item.dataUrl, text_content: item.textContent || null })),
      provider: selectedProvider === "auto" ? null : selectedProvider,
      model: selectedModel === "auto" ? null : selectedModel,
    };

    try {
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (response.status === 404) {
        await sendLegacyRequest(payload);
      } else {
        if (!response.ok) {
          let detail = "حدث خطأ في الـBackend";
          try { detail = (await response.json())?.detail || detail; } catch {}
          throw new Error(detail);
        }
        await readSSEStream(response, (eventName, data) => {
          if (eventName === "meta") {
            const id = typeof data.conversation_id === "string" ? data.conversation_id : null;
            if (id) { setConversationId(id); localStorage.setItem(CONVERSATION_KEY, id); }
            updateAssistantMeta({ webSearch: data.web_search === true, provider: typeof data.provider === "string" ? data.provider : undefined, model: typeof data.model === "string" ? data.model : undefined, task: typeof data.task === "string" ? data.task : undefined });
            if (typeof data.provider === "string") setActiveEngine(data.provider === "brain-orchestrator" ? "Adaptive Brain" : `${data.provider}${data.model ? ` · ${data.model}` : ""}`);
            return;
          }
          if (eventName === "sources") {
            const incoming = Array.isArray(data.sources) ? data.sources.filter((item): item is Source => !!item && typeof item === "object" && typeof (item as Source).url === "string") : [];
            if (incoming.length) updateAssistantMeta({ sources: incoming, webSearch: true });
            return;
          }
          if (eventName === "delta") {
            const chunk = typeof data.text === "string" ? data.text : "";
            if (!chunk) return;
            setMessages((current) => {
              const next = [...current];
              const index = next.findIndex((item) => item.id === assistantId);
              if (index >= 0) next[index] = { ...next[index], content: next[index].content + chunk };
              return next;
            });
            return;
          }
          if (eventName === "done") {
            if (typeof data.provider === "string") setActiveEngine(data.provider === "brain-orchestrator" ? "Adaptive Brain" : `${data.provider}${data.model ? ` · ${data.model}` : ""}`);
            const id = typeof data.conversation_id === "string" ? data.conversation_id : null;
            if (id) { setConversationId(id); localStorage.setItem(CONVERSATION_KEY, id); }
            const finalSources = Array.isArray(data.sources) ? data.sources.filter((item): item is Source => !!item && typeof item === "object" && typeof (item as Source).url === "string") : [];
            updateAssistantMeta({ webSearch: data.web_search === true, sources: finalSources });
            return;
          }
          if (eventName === "error") updateAssistant(`⚠️ ${typeof data.error === "string" ? data.error : "حصل خطأ أثناء التوليد"}`);
        });
      }
      await loadConversations();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") showNotice("تم إيقاف التوليد");
      else {
        console.error("Send message error", error);
        const errorText = error instanceof Error ? error.message : "خطأ غير معروف";
        setMessages((current) => {
          const next = [...current];
          const index = next.findIndex((item) => item.id === assistantId);
          if (index >= 0) next[index] = { ...next[index], content: `⚠️ تعذر تنفيذ الطلب.\n\n\`${errorText}\``, error: true };
          return next;
        });
        setServerOnline(false);
      }
    } finally {
      abortControllerRef.current = null;
      setLoading(false);
      requestAnimationFrame(() => textareaRef.current?.focus());
    }
  }

  function stopGeneration() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setLoading(false);
  }

  function retryAssistant(index: number) {
    if (loading) return;
    const previousUserEntry = messages.map((item, messageIndex) => ({ item, messageIndex })).slice(0, index).reverse().find(({ item }) => item.role === "user");
    if (!previousUserEntry) return showNotice("مش لاقي الرسالة الأصلية");
    setMessages((current) => current.slice(0, previousUserEntry.messageIndex));
    void sendMessage(previousUserEntry.item.content);
  }

  function editUserMessage(index: number) {
    if (loading) return;
    const item = messages[index];
    if (!item || item.role !== "user") return;
    setMessage(item.content);
    setMessages((current) => current.slice(0, index));
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  function renderMessage(content: string, messageKey: string) {
    return <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      code({ className, children, ...props }) {
        const match = /language-(\w+)/.exec(className || "");
        const code = String(children).replace(/\n$/, "");
        if (!match) return <code className="inline-code" dir="ltr" {...props}>{children}</code>;
        return <div className="code-shell"><div className="code-topbar"><span className="code-language">{match[1]}</span><button type="button" onClick={() => void copyText(code, `code-${messageKey}`)}><Icon name="copy" size={14}/>{copiedKey === `code-${messageKey}` ? "تم النسخ" : "نسخ"}</button></div><pre dir="ltr"><code>{code}</code></pre></div>;
      },
      a({ children, href }) { return <a href={href} target="_blank" rel="noreferrer">{children}</a>; },
      table({ children }) { return <div className="table-scroll"><table>{children}</table></div>; },
    }}>{content}</ReactMarkdown>;
  }

  return (
    <main data-theme={theme} className={`silent-app theme-${theme} ${sidebarOpen ? "sidebar-visible" : "sidebar-hidden"} ${dragActive ? "drag-mode" : ""}`} dir="rtl" onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}>
      <div className="luxury-bg"><span/><span/><span/><i/><i/></div>
      {notice && <div className="lux-toast"><span className="toast-icon"><Icon name="spark" size={16}/></span><span>{notice}</span></div>}
      {dragActive && <div className="drop-overlay"><div><Icon name="folder" size={32}/><strong>اسحب الملفات هنا</strong><small>صور، PDF، نصوص، كود وملفات المستندات</small></div></div>}

      <div className="app-shell">
        <aside className="sidebar">
          <div className="sidebar-top">
            <button className="brand-button" onClick={() => void createNewConversation()} aria-label="Silent AI">
              <span className="brand-logo"><Icon name="spark" size={21}/></span>
              <span><strong>Silent AI</strong><small>Intelligent Workspace</small></span>
            </button>
            <button className="icon-button ghost" onClick={() => setSidebarOpen(false)} title="إخفاء الشريط"><Icon name="panel" size={19}/></button>
          </div>

          <button className="new-chat" onClick={() => void createNewConversation()} disabled={loading}><span><Icon name="plus" size={19}/></span><b>محادثة جديدة</b><kbd>Ctrl K</kbd></button>

          <label className="conversation-search"><Icon name="search" size={17}/><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="ابحث في المحادثات"/><kbd>/</kbd></label>

          <div className="side-heading"><span>المحادثات</span><b>{conversations.length}</b></div>
          <div className="conversation-list">
            {filteredConversations.length === 0 ? <div className="side-empty"><span><Icon name="message" size={22}/></span><b>{search ? "مفيش نتائج" : "لسه مفيش محادثات"}</b><small>{search ? "جرّب كلمة مختلفة" : "ابدأ أول محادثة من هنا"}</small></div> : filteredConversations.map((conversation) => (
              <div className={`conversation-item ${conversation.id === conversationId ? "active" : ""}`} key={conversation.id}>
                <button className="conversation-main" onClick={() => void loadConversation(conversation.id)} disabled={loading}><span className="conversation-icon"><Icon name="message" size={16}/></span><span>{conversation.title}</span></button>
                <button className="conversation-more" onClick={() => setActiveMenu(activeMenu === conversation.id ? null : conversation.id)}><Icon name="dots" size={17}/></button>
                {activeMenu === conversation.id && <div className="conversation-menu"><button onClick={() => { setActiveMenu(null); void deleteConversation(conversation.id); }}><Icon name="trash" size={15}/> حذف</button></div>}
              </div>
            ))}
          </div>

          <div className="sidebar-bottom">
            <div className="engine-card"><div className="engine-icon"><Icon name="zap" size={17}/></div><div><b>Adaptive Brain</b><small>{catalog ? `${catalog.providers.filter((item) => item.configured).length} مزود متصل · ${catalog.free_model_count || 0} نموذج مجاني مكتشف` : "Auto routing · جاهز"}</small></div><span className={serverOnline === false ? "offline" : "online"}/></div>
            <div className="privacy-card"><Icon name="shield" size={16}/><span>مساحة خاصة لمحادثاتك</span></div>
          </div>
        </aside>

        <section className="workspace">
          <header className="topbar">
            <div className="topbar-side">
              {!sidebarOpen && <button className="icon-button" onClick={() => setSidebarOpen(true)} title="إظهار القائمة"><Icon name="menu" size={20}/></button>}
              <div className="mobile-brand"><span className="brand-logo small"><Icon name="spark" size={17}/></span><b>Silent AI</b></div>
            </div>
            <div className="session-center"><b>{activeConversation?.title || "محادثة جديدة"}</b><span><i className={serverOnline === false ? "offline-dot" : ""}/>{activeEngine} · {serverOnline === false ? "غير متصل" : "جاهز"}</span></div>
            <div className="topbar-actions">
              <div className="model-picker">
                <button className="model-picker-button" onClick={() => setModelMenuOpen((value) => !value)} title="اختيار النموذج">
                  <span className="model-dot"/>
                  <span>{selectedModel === "auto" ? "Auto Brain" : selectedModel}</span>
                  <Icon name="chevron" size={14}/>
                </button>
                {modelMenuOpen && <div className="model-menu">
                  <button className={selectedModel === "auto" ? "active" : ""} onClick={() => { setSelectedProvider("auto"); setSelectedModel("auto"); setModelMenuOpen(false); }}><span className="model-menu-dot auto"/><div><b>Auto Brain</b><small>يحلل السؤال ويختار المسار الأنسب</small></div></button>
                  {(catalog?.providers || []).map((item) => <div className="model-group" key={item.id}>
                    <div className="model-group-title"><span>{item.name}</span><small>{item.configured ? "متصل" : "غير متصل"}</small></div>
                    {item.models.slice(0, 8).map((model) => <button key={`${item.id}-${model}`} disabled={!item.configured} className={selectedModel === model && selectedProvider === item.id ? "active" : ""} onClick={() => { setSelectedProvider(item.id); setSelectedModel(model); setModelMenuOpen(false); }}><span className="model-menu-dot"/><div><b>{model}</b><small>{item.configured ? "استخدام مباشر" : "مفتاح غير متاح"}</small></div></button>)}
                  </div>)}
                </div>}
              </div>
              <button className="theme-button" type="button" onClick={toggleTheme} aria-pressed={theme === "light"} title={theme === "dark" ? "التبديل إلى الوضع النهاري" : "التبديل إلى الوضع الليلي"}><span className="theme-icon">{theme === "dark" ? <Icon name="sun" size={17}/> : <Icon name="moon" size={17}/>}</span><span>{theme === "dark" ? "نهاري" : "ليلي"}</span></button>
              <button className="icon-button" onClick={() => void createNewConversation()} title="محادثة جديدة"><Icon name="plus" size={20}/></button>
            </div>
          </header>

          <section className="chat-scroll">
            {messages.length === 0 ? (
              <div className="hero">
                <div className="hero-badge"><span><Icon name="spark" size={14}/></span> SILENT AI · COGNITIVE WORKSPACE</div>
                <div className="hero-symbol"><div className="orbit orbit-a"/><div className="orbit orbit-b"/><div className="hero-core"><Icon name="spark" size={28}/></div></div>
                <h1>مخّك الرقمي.<br/><em>بواجهة تستحقه.</em></h1>
                <p>فكّر بصوتك أو اكتب براحتك. ارفع ملف، صورة، أو لقطة من الكاميرا<br/>وسيحوّل Silent AI الفكرة الخام إلى إجابة واضحة، دقيقة، وقابلة للتنفيذ.</p>
                <div className="quick-grid">
                  <button onClick={() => setSuggestion("ابنيلي خطة كاملة لمشروعي خطوة بخطوة") }><span className="quick-icon purple"><Icon name="zap" size={19}/></span><div><b>خطط وبناء</b><small>حوّل الفكرة إلى خطوات تنفيذ</small></div><Icon name="arrow" size={17}/></button>
                  <button onClick={() => setSuggestion("اشرحلي الموضوع ده بطريقة بسيطة وعملية مع أمثلة") }><span className="quick-icon blue"><Icon name="message" size={19}/></span><div><b>شرح وتحليل</b><small>افهم أي موضوع بوضوح</small></div><Icon name="arrow" size={17}/></button>
                  <button onClick={() => setSuggestion("راجع الكود ده واكتشف الأخطاء وحسّنه") }><span className="quick-icon green"><Icon name="file" size={19}/></span><div><b>برمجة وكود</b><small>راجع، أصلح وطوّر</small></div><Icon name="arrow" size={17}/></button>
                  <button onClick={() => imageInputRef.current?.click()}><span className="quick-icon orange"><Icon name="image" size={19}/></span><div><b>تحليل الصور</b><small>ارفع صورة واسأل عنها</small></div><Icon name="arrow" size={17}/></button>
                </div>
                <div className="hero-trust"><span><i className="signal-dot"/> النظام جاهز</span><span><Icon name="zap" size={14}/> Adaptive Brain</span><span><Icon name="shield" size={14}/> خصوصية أولاً</span><span><Icon name="paperclip" size={14}/> ملفات · صور · كاميرا</span></div>
              </div>
            ) : (
              <div className="message-column">
                {messages.map((msg, index) => {
                  const isUser = msg.role === "user";
                  const isLast = index === messages.length - 1;
                  const isGenerating = !isUser && isLast && loading;
                  const messageKey = msg.id;
                  return <article className={`message-block ${isUser ? "user-block" : "assistant-block"}`} key={messageKey}>
                    {!isUser && <div className="assistant-avatar"><Icon name="spark" size={16}/></div>}
                    <div className="message-body">
                      {isUser ? <>
                        {msg.attachments?.length ? <div className="message-attachments">{msg.attachments.map((item) => item.type.startsWith("image/") ? <div className="sent-image" key={item.id}><img src={item.dataUrl} alt={item.name}/><span>{item.name}</span></div> : <div className="sent-file" key={item.id}><Icon name="file" size={18}/><div><b>{item.name}</b><small>{formatSize(item.size)}</small></div></div>)}</div> : null}
                        <div className="user-bubble">{msg.content}</div>
                        {!loading && <div className="message-toolbar user-toolbar"><button onClick={() => void copyText(msg.content, `copy-${messageKey}`)}><Icon name="copy" size={14}/>{copiedKey === `copy-${messageKey}` ? "تم" : "نسخ"}</button><button onClick={() => editUserMessage(index)}><Icon name="edit" size={14}/>تعديل</button></div>}
                      </> : <>
                        <div className={`assistant-content ${msg.error ? "has-error" : ""}`}>
                          {msg.content ? renderMessage(msg.content, messageKey) : isGenerating ? <div className="thinking"><span/><span/><span/><b>بيفكّر في أفضل رد...</b></div> : null}
                          {isGenerating && msg.content && <span className="typing-cursor"/>}
                          {!loading && msg.sources?.length ? <div className="web-sources"><div className="sources-title"><span><Icon name="search" size={14}/></span><b>مصادر الويب</b><small>{msg.sources.length}</small></div>{msg.sources.map((source, sourceIndex) => <a key={`${messageKey}-${sourceIndex}`} href={source.url} target="_blank" rel="noreferrer"><span className="source-num">{sourceIndex + 1}</span><div><b>{source.title}</b><small>{(() => { try { return new URL(source.url).hostname.replace(/^www\./, ""); } catch { return source.url; } })()}</small></div><Icon name="arrow" size={14}/></a>)}</div> : null}
                        </div>
                        {!loading && msg.content && !msg.error && <><div className="message-meta"><span>{msg.provider === "brain-orchestrator" ? "Adaptive Brain" : msg.provider || "Auto"}</span>{msg.model && msg.model !== "verified" && <span>{msg.model}</span>}{msg.task && <span>{msg.task}</span>}</div><div className="message-toolbar"><button onClick={() => void copyText(msg.content, `copy-${messageKey}`)}><Icon name="copy" size={14}/>{copiedKey === `copy-${messageKey}` ? "تم النسخ" : "نسخ"}</button><button onClick={() => retryAssistant(index)}><Icon name="refresh" size={14}/>إعادة</button></div></>}
                      </>}
                    </div>
                  </article>;
                })}
                <div ref={messagesEndRef} className="messages-end"/>
              </div>
            )}
          </section>

          <div className="composer-zone">
            {attachments.length > 0 && <div className="attachment-strip">{attachments.map((item) => <div className="attachment-card" key={item.id}>{item.type.startsWith("image/") ? <img src={item.dataUrl} alt={item.name}/> : <span className="file-preview-icon"><Icon name="file" size={19}/></span>}<div><b>{item.name}</b><small>{item.type.startsWith("image/") ? "صورة جاهزة للتحليل" : `${formatSize(item.size)} · ملف جاهز`}</small></div><button onClick={() => removeAttachment(item.id)} title="إزالة"><Icon name="x" size={15}/></button></div>)}</div>}

            <div className="composer-shell">
              <div className="composer-topline"><span><i/> SILENT CORE <b>ONLINE</b></span><small>{attachments.length ? `${attachments.length} مرفق جاهز` : "اسحب الملفات هنا أو ابدأ الكتابة"}</small></div>
              <div className="composer" onClick={() => textareaRef.current?.focus()}>
                <button className="attach-main" onClick={(event) => { event.stopPropagation(); setShowAttachMenu((value) => !value); }} disabled={loading} title="إضافة صورة أو ملف"><Icon name="plus" size={21}/></button>
                <textarea ref={textareaRef} value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void sendMessage(); } }} placeholder="اكتب رسالتك لـ Silent AI..." rows={1} disabled={loading}/>
                <button className="composer-camera" onClick={(event) => { event.stopPropagation(); void openCamera(); }} disabled={loading} title="التقاط صورة بالكاميرا"><Icon name="camera" size={20}/></button>
                {loading ? <button className="send-button stop" onClick={(event) => { event.stopPropagation(); stopGeneration(); }} title="إيقاف"><Icon name="stop" size={17}/></button> : <button className="send-button" onClick={(event) => { event.stopPropagation(); void sendMessage(); }} disabled={!message.trim() && !attachments.length} title="إرسال"><Icon name="send" size={19}/></button>}
              </div>
              <div className="composer-bottom"><span>↵ إرسال</span><span>Shift + ↵ سطر جديد</span><span className="desktop-only">صور · ملفات · كاميرا · بحث ويب</span></div>

              {showAttachMenu && <div className="attach-menu">
                <button onClick={() => imageInputRef.current?.click()}><span className="menu-icon image"><Icon name="image" size={19}/></span><div><b>صورة</b><small>JPG · PNG · WEBP</small></div></button>
                <button onClick={() => fileInputRef.current?.click()}><span className="menu-icon file"><Icon name="file" size={19}/></span><div><b>ملف</b><small>PDF · DOCX · TXT · CSV · كود</small></div></button>
                <button onClick={() => void openCamera()}><span className="menu-icon camera"><Icon name="camera" size={19}/></span><div><b>الكاميرا</b><small>التقط صورة الآن</small></div></button>
              </div>}
            </div>
            <div className="disclaimer"><Icon name="shield" size={13}/> Silent AI قد يخطئ. راجع المعلومات المهمة قبل الاعتماد عليها.</div>
          </div>

          <input ref={imageInputRef} type="file" accept="image/*" multiple hidden onChange={handleImageSelect}/>
          <input ref={fileInputRef} type="file" accept="image/*,.pdf,.txt,.md,.markdown,.csv,.json,.xml,.yaml,.yml,.js,.jsx,.ts,.tsx,.py,.java,.c,.cpp,.h,.css,.html,.sql,.sh,.ps1,.docx,.xlsx,.log" multiple hidden onChange={handleFileSelect}/>
        </section>
      </div>

      {showCamera && <div className="camera-modal" role="dialog" aria-modal="true">
        <div className="camera-card">
          <div className="camera-header"><div><b>التقاط صورة</b><small>صوّر أي شيء وسيظهر مباشرة في المحادثة</small></div><button onClick={closeCamera}><Icon name="x" size={20}/></button></div>
          <div className="camera-view"><video ref={videoRef} playsInline muted/><div className="camera-corners"><i/><i/><i/><i/></div><div className="camera-status"><span/><small>الكاميرا جاهزة</small></div></div>
          <div className="camera-actions"><button className="camera-cancel" onClick={closeCamera}>إلغاء</button><button className="capture-button" onClick={captureCamera}><span><Icon name="camera" size={22}/></span>التقاط الصورة</button></div>
        </div>
      </div>}
    </main>
  );
}
