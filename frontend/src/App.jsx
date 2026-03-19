import "./App.css";
import { useEffect, useMemo, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";

const API_BASE = "http://127.0.0.1:8000";
const STORAGE_KEY = "sound_ai_tool_ui_state_v1";

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return "00:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function loadPersistedState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function savePersistedState(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    //
  }
}

function Toast({ toasts, onRemove }) {
  return (
    <div className="toast-wrap">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.type || "info"}`}>
          <div className="toast-text">{toast.text}</div>
          <button className="toast-close" onClick={() => onRemove(toast.id)}>
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

function WaveformPlayer({
  audioUrl,
  isActive,
  onPlayRequest,
  title = "Audio",
  compact = false,
}) {
  const waveformRef = useRef(null);
  const wavesurferRef = useRef(null);

  const [isReady, setIsReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);

  useEffect(() => {
    if (!waveformRef.current || !audioUrl) return;

    const ws = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: "#7c8aa5",
      progressColor: "#4f7cff",
      cursorColor: "#222",
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: compact ? 64 : 80,
      normalize: true,
      responsive: true,
    });

    wavesurferRef.current = ws;
    setIsReady(false);
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);

    ws.load(audioUrl);

    ws.on("ready", () => {
      setIsReady(true);
      setDuration(ws.getDuration() || 0);
      ws.setVolume(volume);
    });

    ws.on("play", () => {
      setIsPlaying(true);
    });

    ws.on("pause", () => {
      setIsPlaying(false);
    });

    ws.on("finish", () => {
      setIsPlaying(false);
      setCurrentTime(0);
    });

    ws.on("timeupdate", (time) => {
      setCurrentTime(time || 0);
    });

    return () => {
      try {
        ws.destroy();
      } catch {
        //
      }
    };
  }, [audioUrl, compact]);

  useEffect(() => {
    if (!isActive && wavesurferRef.current?.isPlaying()) {
      wavesurferRef.current.pause();
    }
  }, [isActive]);

  useEffect(() => {
    if (wavesurferRef.current) {
      wavesurferRef.current.setVolume(volume);
    }
  }, [volume]);

  const handleTogglePlay = () => {
    if (!wavesurferRef.current || !isReady) return;
    if (!isPlaying && onPlayRequest) onPlayRequest();
    wavesurferRef.current.playPause();
  };

  const handleStop = () => {
    if (!wavesurferRef.current || !isReady) return;
    wavesurferRef.current.stop();
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const handleRestart = () => {
    if (!wavesurferRef.current || !isReady) return;
    if (onPlayRequest) onPlayRequest();
    wavesurferRef.current.stop();
    wavesurferRef.current.play();
  };

  return (
    <div className={`waveform-player ${compact ? "compact" : ""}`}>
      <div className="waveform-top">
        <div className="waveform-title">{title}</div>
        <div className="waveform-time">
          {formatTime(currentTime)} / {formatTime(duration)}
        </div>
      </div>

      <div className="waveform" ref={waveformRef}></div>

      <div className="player-controls">
        <button onClick={handleTogglePlay} disabled={!isReady}>
          {!isReady ? "Loading..." : isPlaying ? "Pause" : "Play"}
        </button>
        <button onClick={handleStop} disabled={!isReady}>
          Stop
        </button>
        <button onClick={handleRestart} disabled={!isReady}>
          Restart
        </button>

        <div className="volume-box">
          <span>Vol</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
          />
          <span>{Math.round(volume * 100)}</span>
        </div>
      </div>
    </div>
  );
}

function AudioItem({
  file,
  index,
  layerOptions,
  presets,
  onSave,
  onApplyLayer,
  onDelete,
  onToggleFavorite,
  onRename,
  onSavePreset,
  onDeletePreset,
  isActive,
  onPlayRequest,
  isSaving,
  isLayering,
  isSelected,
  onToggleSelect,
}) {
  const categoryKeys = Object.keys(layerOptions || {});
  const defaultCategory = categoryKeys[0] || "";

  const [category, setCategory] = useState(defaultCategory);
  const [subType, setSubType] = useState(
    defaultCategory && layerOptions[defaultCategory]?.length > 0
      ? layerOptions[defaultCategory][0]
      : ""
  );
  const [layerGain, setLayerGain] = useState(-8);
  const [positionMs, setPositionMs] = useState(0);
  const [editingName, setEditingName] = useState(false);
  const [draftName, setDraftName] = useState(file.displayName || file.filename);
  const [presetName, setPresetName] = useState("");
  const presetKeys = Object.keys(presets || {});
  const [selectedPreset, setSelectedPreset] = useState("");

  useEffect(() => {
    setDraftName(file.displayName || file.filename);
  }, [file.displayName, file.filename]);

  useEffect(() => {
    if (!category) return;
    const subTypes = layerOptions[category] || [];
    if (subTypes.length > 0 && !subTypes.includes(subType)) {
      setSubType(subTypes[0]);
    } else if (subTypes.length === 0) {
      setSubType("");
    }
  }, [category, layerOptions, subType]);

  const handleLayer = async () => {
    if (!category || !subType) {
      alert("레이어 카테고리와 타입을 선택해줘.");
      return;
    }

    await onApplyLayer(file.filename, category, subType, layerGain, positionMs);
  };

  const handleRenameSave = () => {
    const trimmed = draftName.trim();
    if (!trimmed) {
      setDraftName(file.displayName || file.filename);
      setEditingName(false);
      return;
    }

    onRename(file.filename, trimmed);
    setEditingName(false);
  };

  const applyPreset = (presetKey) => {
    setSelectedPreset(presetKey);
    const preset = presets?.[presetKey];
    if (!preset) return;

    setCategory(preset.category || defaultCategory);
    setSubType(preset.sub_type || "");
    setLayerGain(
      typeof preset.layer_gain === "number" ? preset.layer_gain : -8
    );
    setPositionMs(
      typeof preset.position_ms === "number" ? preset.position_ms : 0
    );
  };

  const handleSavePresetClick = () => {
    const trimmed = presetName.trim();
    if (!trimmed) {
      alert("프리셋 이름을 입력해줘.");
      return;
    }
    onSavePreset(trimmed, category, subType, layerGain, positionMs);
    setPresetName("");
  };

  return (
    <div className={`audio-item ${isActive ? "active" : ""}`}>
      <div className="audio-header">
        <div className="audio-left">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(file.filename)}
          />

          <button
            className={`favorite-btn ${file.favorite ? "on" : ""}`}
            onClick={() => onToggleFavorite(file.filename)}
            title="Favorite"
          >
            ★
          </button>

          <div className="audio-title-wrap">
            <div className="audio-top-line">
              <strong>
                {file.type === "layered"
                  ? "Layered Result"
                  : `Variation ${index + 1}`}
              </strong>

              <div className="tag-group">
                <span
                  className={`tag ${
                    file.type === "layered" ? "purple" : "blue"
                  }`}
                >
                  {file.type}
                </span>
                {file.favorite && <span className="tag gold">favorite</span>}
                {file.saved && <span className="tag green">saved</span>}
              </div>
            </div>

            {!editingName ? (
              <div className="filename-row">
                <span className="display-name">
                  {file.displayName || file.filename}
                </span>
                <button className="mini-btn" onClick={() => setEditingName(true)}>
                  Rename
                </button>
              </div>
            ) : (
              <div className="rename-row">
                <input
                  value={draftName}
                  onChange={(e) => setDraftName(e.target.value)}
                />
                <button className="mini-btn" onClick={handleRenameSave}>
                  Save
                </button>
                <button
                  className="mini-btn ghost"
                  onClick={() => setEditingName(false)}
                >
                  Cancel
                </button>
              </div>
            )}

            <span className="raw-filename">{file.filename}</span>
          </div>
        </div>

        <button className="delete-btn" onClick={() => onDelete(file.filename)}>
          Delete
        </button>
      </div>

      <WaveformPlayer
        audioUrl={file.preview_url}
        isActive={isActive}
        onPlayRequest={onPlayRequest}
        title={file.displayName || file.filename}
      />

      <div className="audio-actions">
        <button onClick={() => onSave(file.filename)} disabled={isSaving}>
          {isSaving ? "Saving..." : file.saved ? "Saved" : "Save"}
        </button>

        <a href={`${API_BASE}/download/${file.filename}`} download>
          <button>Download</button>
        </a>
      </div>

      <div className="layer-panel">
        <h4>Layer Options</h4>

        <div className="preset-box">
          <div className="preset-row">
            <select
              value={selectedPreset}
              onChange={(e) => applyPreset(e.target.value)}
            >
              <option value="">Preset 선택</option>
              {presetKeys.map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>

            <button
              className="mini-btn"
              onClick={() => selectedPreset && onDeletePreset(selectedPreset)}
              disabled={!selectedPreset}
            >
              Delete Preset
            </button>
          </div>

          <div className="preset-row">
            <input
              type="text"
              placeholder="새 프리셋 이름"
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
            />
            <button className="mini-btn" onClick={handleSavePresetClick}>
              Save Preset
            </button>
          </div>
        </div>

        <div className="layer-grid">
          <div className="layer-row">
            <label>Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {categoryKeys.map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>
          </div>

          <div className="layer-row">
            <label>Type</label>
            <select value={subType} onChange={(e) => setSubType(e.target.value)}>
              {(layerOptions[category] || []).map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          <div className="layer-row">
            <label>Layer Gain (dB)</label>
            <input
              type="number"
              value={layerGain}
              onChange={(e) => setLayerGain(Number(e.target.value))}
            />
          </div>

          <div className="layer-row">
            <label>Position (ms)</label>
            <input
              type="number"
              min="0"
              value={positionMs}
              onChange={(e) => setPositionMs(Number(e.target.value))}
            />
          </div>
        </div>

        <button onClick={handleLayer} disabled={isLayering}>
          {isLayering ? "Layering..." : "Apply Layer"}
        </button>
      </div>
    </div>
  );
}

function App() {
  const persisted = loadPersistedState();

  const [count, setCount] = useState(10);
  const [message, setMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedFileUrl, setSelectedFileUrl] = useState(null);
  const [files, setFiles] = useState([]);
  const [layerOptions, setLayerOptions] = useState({});

  const [isGenerating, setIsGenerating] = useState(false);
  const [savingMap, setSavingMap] = useState({});
  const [layeringMap, setLayeringMap] = useState({});
  const [activePlayer, setActivePlayer] = useState(null);

  const [toasts, setToasts] = useState([]);
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [sortType, setSortType] = useState("latest");
  const [selectedItems, setSelectedItems] = useState([]);

  const [favoriteMap, setFavoriteMap] = useState(persisted.favoriteMap || {});
  const [savedMap, setSavedMap] = useState(persisted.savedMap || {});
  const [renameMap, setRenameMap] = useState(persisted.renameMap || {});
  const [historyItems, setHistoryItems] = useState([]);
  const [presets, setPresets] = useState({});

  useEffect(() => {
    fetchLayerOptions();
    fetchDisplayNames();
    fetchHistory();
    fetchPresets();
  }, []);

  useEffect(() => {
    savePersistedState({
      favoriteMap,
      savedMap,
      renameMap,
    });
  }, [favoriteMap, savedMap, renameMap]);

  useEffect(() => {
    return () => {
      if (selectedFileUrl) {
        URL.revokeObjectURL(selectedFileUrl);
      }
    };
  }, [selectedFileUrl]);

  const pushToast = (text, type = "info") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, text, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
    }, 2600);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  };

  const fetchLayerOptions = async () => {
    try {
      const response = await fetch(`${API_BASE}/layer-options`);
      const data = await response.json();
      setLayerOptions(data.options || {});
    } catch (error) {
      console.error("레이어 옵션 불러오기 실패:", error);
      pushToast("레이어 옵션 불러오기 실패", "error");
    }
  };

  const fetchDisplayNames = async () => {
    try {
      const response = await fetch(`${API_BASE}/display-names`);
      const data = await response.json();
      const names = data.display_names || {};
      setRenameMap(names);

      setFiles((prev) =>
        prev.map((file) => ({
          ...file,
          displayName: names[file.filename] || file.displayName || file.filename,
        }))
      );
    } catch (error) {
      console.error("display names load error", error);
    }
  };

  const fetchHistory = async () => {
    try {
      const response = await fetch(`${API_BASE}/history?limit=30`);
      const data = await response.json();
      setHistoryItems(data.history || []);
    } catch (error) {
      console.error("history load error", error);
    }
  };

  const fetchPresets = async () => {
    try {
      const response = await fetch(`${API_BASE}/presets`);
      const data = await response.json();
      setPresets(data.presets || {});
    } catch (error) {
      console.error("preset load error", error);
    }
  };

  const buildDecoratedFiles = (rawFiles) => {
    return rawFiles.map((file, idx) => ({
      ...file,
      _order: Date.now() + idx,
      favorite: !!favoriteMap[file.filename],
      saved: !!savedMap[file.filename],
      displayName: renameMap[file.filename] || file.filename,
    }));
  };

  const handleFileSelect = (file) => {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".wav")) {
      pushToast("WAV 파일만 업로드 가능해.", "error");
      return;
    }

    setSelectedFile(file);

    if (selectedFileUrl) URL.revokeObjectURL(selectedFileUrl);
    const nextUrl = URL.createObjectURL(file);
    setSelectedFileUrl(nextUrl);

    pushToast(`선택됨: ${file.name}`, "success");
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();

    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  };

  const handleGenerate = async () => {
    if (!selectedFile) {
      setMessage("먼저 WAV 파일을 선택해줘.");
      pushToast("먼저 WAV 파일을 선택해줘.", "error");
      return;
    }

    setIsGenerating(true);
    setMessage("생성 중...");
    setFiles([]);
    setSelectedItems([]);
    setActivePlayer(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("num", count);

      const response = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ? JSON.stringify(data.detail) : "생성 실패");
      }

      const decorated = buildDecoratedFiles(data.files || []);
      setFiles(decorated);
      setMessage(`생성 완료: ${decorated.length}개`);
      pushToast(`생성 완료: ${decorated.length}개`, "success");
      fetchHistory();
    } catch (error) {
      setMessage(`에러 발생: ${error.message}`);
      pushToast(`생성 실패: ${error.message}`, "error");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async (filename) => {
    setSavingMap((prev) => ({ ...prev, [filename]: true }));

    try {
      const response = await fetch(`${API_BASE}/save/${filename}`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "저장 실패");
      }

      setSavedMap((prev) => ({ ...prev, [filename]: true }));
      setFiles((prev) =>
        prev.map((file) =>
          file.filename === filename ? { ...file, saved: true } : file
        )
      );
      pushToast(`${filename} 저장 완료`, "success");
      fetchHistory();
    } catch (error) {
      pushToast(`저장 에러: ${error.message}`, "error");
    } finally {
      setSavingMap((prev) => ({ ...prev, [filename]: false }));
    }
  };

  const handleBulkSave = async () => {
    if (selectedItems.length === 0) {
      pushToast("선택된 항목이 없어.", "error");
      return;
    }

    for (const filename of selectedItems) {
      await handleSave(filename);
    }
  };

  const handleBulkDownload = async () => {
    if (selectedItems.length === 0) {
      pushToast("선택된 항목이 없어.", "error");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("filenames", selectedItems.join(","));

      const response = await fetch(`${API_BASE}/bulk-download`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let message = "zip 다운로드 실패";
        try {
          const err = await response.json();
          message = err.detail || message;
        } catch {
          //
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "sound_ai_selected.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

      pushToast("ZIP 다운로드 완료", "success");
      fetchHistory();
    } catch (error) {
      pushToast(`ZIP 다운로드 에러: ${error.message}`, "error");
    }
  };

  const handleApplyLayer = async (
    filename,
    category,
    subType,
    layerGain,
    positionMs
  ) => {
    setLayeringMap((prev) => ({ ...prev, [filename]: true }));

    try {
      const formData = new FormData();
      formData.append("filename", filename);
      formData.append("category", category);
      formData.append("sub_type", subType);
      formData.append("layer_gain", layerGain);
      formData.append("position_ms", positionMs);

      const response = await fetch(`${API_BASE}/apply-layer`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "레이어 적용 실패");
      }

      const nextFile = {
        ...data,
        _order: Date.now(),
        favorite: !!favoriteMap[data.filename],
        saved: !!savedMap[data.filename],
        displayName: renameMap[data.filename] || data.filename,
      };

      setFiles((prev) => [nextFile, ...prev]);
      setMessage(
        `레이어 적용 완료: ${category} / ${subType} / gain ${layerGain}dB / ${positionMs}ms`
      );
      pushToast("레이어 적용 완료", "success");
      fetchHistory();
    } catch (error) {
      pushToast(`레이어 에러: ${error.message}`, "error");
    } finally {
      setLayeringMap((prev) => ({ ...prev, [filename]: false }));
    }
  };

  const handleDelete = async (filename) => {
    const ok = window.confirm(`${filename} 을(를) 정말 삭제할까?`);
    if (!ok) return;

    try {
      const response = await fetch(`${API_BASE}/delete/${filename}`, {
        method: "DELETE",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "삭제 실패");
      }

      setFiles((prev) => prev.filter((file) => file.filename !== filename));
      setSelectedItems((prev) => prev.filter((item) => item !== filename));

      if (activePlayer === filename) {
        setActivePlayer(null);
      }

      pushToast(`${filename} 삭제 완료`, "success");
      fetchHistory();
    } catch (error) {
      pushToast(`삭제 에러: ${error.message}`, "error");
    }
  };

  const handleBulkDelete = async () => {
    if (selectedItems.length === 0) {
      pushToast("선택된 항목이 없어.", "error");
      return;
    }

    const ok = window.confirm(`${selectedItems.length}개 항목을 삭제할까?`);
    if (!ok) return;

    for (const filename of selectedItems) {
      try {
        const response = await fetch(`${API_BASE}/delete/${filename}`, {
          method: "DELETE",
        });
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || "삭제 실패");
        }
      } catch (error) {
        pushToast(`${filename} 삭제 실패: ${error.message}`, "error");
      }
    }

    setFiles((prev) =>
      prev.filter((file) => !selectedItems.includes(file.filename))
    );
    if (selectedItems.includes(activePlayer)) {
      setActivePlayer(null);
    }
    pushToast(`${selectedItems.length}개 삭제 완료`, "success");
    setSelectedItems([]);
    fetchHistory();
  };

  const handleToggleFavorite = (filename) => {
    const next = !favoriteMap[filename];

    setFavoriteMap((prev) => ({ ...prev, [filename]: next }));
    setFiles((prev) =>
      prev.map((file) =>
        file.filename === filename ? { ...file, favorite: next } : file
      )
    );
  };

  const handleRename = async (filename, newName) => {
    try {
      const formData = new FormData();
      formData.append("filename", filename);
      formData.append("display_name", newName);

      const response = await fetch(`${API_BASE}/rename`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "이름 변경 실패");
      }

      setRenameMap((prev) => ({ ...prev, [filename]: newName }));
      setFiles((prev) =>
        prev.map((file) =>
          file.filename === filename ? { ...file, displayName: newName } : file
        )
      );

      pushToast("표시 이름 변경 완료", "success");
      fetchHistory();
    } catch (error) {
      pushToast(`이름 변경 에러: ${error.message}`, "error");
    }
  };

  const handleSavePreset = async (
    presetName,
    category,
    subType,
    layerGain,
    positionMs
  ) => {
    try {
      const formData = new FormData();
      formData.append("preset_name", presetName);
      formData.append("category", category);
      formData.append("sub_type", subType);
      formData.append("layer_gain", layerGain);
      formData.append("position_ms", positionMs);

      const response = await fetch(`${API_BASE}/presets`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "프리셋 저장 실패");
      }

      pushToast("프리셋 저장 완료", "success");
      fetchPresets();
      fetchHistory();
    } catch (error) {
      pushToast(`프리셋 저장 에러: ${error.message}`, "error");
    }
  };

  const handleDeletePreset = async (presetName) => {
    try {
      const response = await fetch(
        `${API_BASE}/presets/${encodeURIComponent(presetName)}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "프리셋 삭제 실패");
      }

      pushToast("프리셋 삭제 완료", "success");
      fetchPresets();
      fetchHistory();
    } catch (error) {
      pushToast(`프리셋 삭제 에러: ${error.message}`, "error");
    }
  };

  const handleToggleSelect = (filename) => {
    setSelectedItems((prev) =>
      prev.includes(filename)
        ? prev.filter((item) => item !== filename)
        : [...prev, filename]
    );
  };

  const filteredFiles = useMemo(() => {
    let next = [...files];

    if (filterType === "variation") {
      next = next.filter((file) => file.type === "variation");
    } else if (filterType === "layered") {
      next = next.filter((file) => file.type === "layered");
    } else if (filterType === "favorite") {
      next = next.filter((file) => file.favorite);
    } else if (filterType === "saved") {
      next = next.filter((file) => file.saved);
    }

    if (search.trim()) {
      const keyword = search.trim().toLowerCase();
      next = next.filter(
        (file) =>
          file.filename.toLowerCase().includes(keyword) ||
          (file.displayName || "").toLowerCase().includes(keyword)
      );
    }

    if (sortType === "latest") {
      next.sort((a, b) => (b._order || 0) - (a._order || 0));
    } else if (sortType === "oldest") {
      next.sort((a, b) => (a._order || 0) - (b._order || 0));
    } else if (sortType === "name") {
      next.sort((a, b) =>
        (a.displayName || a.filename).localeCompare(
          b.displayName || b.filename
        )
      );
    } else if (sortType === "type") {
      next.sort((a, b) => a.type.localeCompare(b.type));
    }

    return next;
  }, [files, filterType, sortType, search]);

  const handleSelectAllVisible = () => {
    const visibleNames = filteredFiles.map((file) => file.filename);
    const allSelected =
      visibleNames.length > 0 &&
      visibleNames.every((name) => selectedItems.includes(name));

    if (allSelected) {
      setSelectedItems((prev) =>
        prev.filter((item) => !visibleNames.includes(item))
      );
    } else {
      setSelectedItems((prev) => Array.from(new Set([...prev, ...visibleNames])));
    }
  };

  const selectedVisibleCount = filteredFiles.filter((file) =>
    selectedItems.includes(file.filename)
  ).length;

  return (
    <div className="app">
      <Toast toasts={toasts} onRemove={removeToast} />

      <h1>Sound AI Tool</h1>
      <p className="subtitle">
        생성 후 미리 들어보고 마음에 드는 variation만 저장하세요.
        파형 확인, 비교 청취, 필터링, 레이어 합성까지 한 번에 가능합니다.
      </p>

      <div className="card">
        <div
          className="dropzone"
          onDragOver={(e) => {
            e.preventDefault();
            e.stopPropagation();
          }}
          onDrop={handleDrop}
        >
          <div className="dropzone-title">WAV 파일 업로드</div>
          <div className="dropzone-desc">
            파일을 여기로 드래그하거나 아래 버튼으로 선택
          </div>

          <input
            type="file"
            accept=".wav"
            onChange={(e) => handleFileSelect(e.target.files[0])}
          />

          <div className="selected-file">
            선택한 파일: {selectedFile ? selectedFile.name : "없음"}
          </div>
        </div>

        {selectedFileUrl && (
          <div className="original-panel">
            <h3>Original Preview</h3>
            <WaveformPlayer
              audioUrl={selectedFileUrl}
              isActive={activePlayer === "__original__"}
              onPlayRequest={() => setActivePlayer("__original__")}
              title={selectedFile?.name || "Original"}
              compact
            />
          </div>
        )}

        <div className="generate-grid">
          <div className="field">
            <label>생성 개수</label>
            <input
              type="number"
              min="1"
              max="20"
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
            />
          </div>

          <div className="field generate-btn-wrap">
            <label>&nbsp;</label>
            <button onClick={handleGenerate} disabled={isGenerating}>
              {isGenerating ? "Generating..." : "Generate"}
            </button>
          </div>
        </div>

        <div className="result">{message}</div>
      </div>

      {files.length > 0 && (
        <>
          <div className="toolbar card">
            <div className="toolbar-row">
              <input
                className="search-input"
                type="text"
                placeholder="파일명 검색"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />

              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
              >
                <option value="all">All</option>
                <option value="variation">Variations</option>
                <option value="layered">Layered</option>
                <option value="favorite">Favorites</option>
                <option value="saved">Saved</option>
              </select>

              <select value={sortType} onChange={(e) => setSortType(e.target.value)}>
                <option value="latest">Latest</option>
                <option value="oldest">Oldest</option>
                <option value="name">Name</option>
                <option value="type">Type</option>
              </select>
            </div>

            <div className="toolbar-row">
              <button onClick={handleSelectAllVisible}>
                {selectedVisibleCount === filteredFiles.length &&
                filteredFiles.length > 0
                  ? "Unselect Visible"
                  : "Select Visible"}
              </button>

              <button onClick={handleBulkSave} disabled={selectedItems.length === 0}>
                Save Selected ({selectedItems.length})
              </button>

              <button
                onClick={handleBulkDownload}
                disabled={selectedItems.length === 0}
              >
                Download ZIP ({selectedItems.length})
              </button>

              <button
                className="danger"
                onClick={handleBulkDelete}
                disabled={selectedItems.length === 0}
              >
                Delete Selected ({selectedItems.length})
              </button>
            </div>
          </div>

          <div className="list">
            <h2>Preview Variations</h2>

            {filteredFiles.length === 0 ? (
              <div className="empty-box">조건에 맞는 결과가 없어.</div>
            ) : (
              filteredFiles.map((file, index) => (
                <AudioItem
                  key={file.filename}
                  file={file}
                  index={index}
                  layerOptions={layerOptions}
                  presets={presets}
                  onSave={handleSave}
                  onApplyLayer={handleApplyLayer}
                  onDelete={handleDelete}
                  onToggleFavorite={handleToggleFavorite}
                  onRename={handleRename}
                  onSavePreset={handleSavePreset}
                  onDeletePreset={handleDeletePreset}
                  isActive={activePlayer === file.filename}
                  onPlayRequest={() => setActivePlayer(file.filename)}
                  isSaving={!!savingMap[file.filename]}
                  isLayering={!!layeringMap[file.filename]}
                  isSelected={selectedItems.includes(file.filename)}
                  onToggleSelect={handleToggleSelect}
                />
              ))
            )}
          </div>
        </>
      )}

      <div className="card">
        <h2>Recent History</h2>
        {historyItems.length === 0 ? (
          <div className="empty-box">기록이 없어.</div>
        ) : (
          <div className="history-list">
            {historyItems.map((item, idx) => (
              <div key={idx} className="history-item">
                <strong>{item.action}</strong>
                <pre>{JSON.stringify(item, null, 2)}</pre>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;