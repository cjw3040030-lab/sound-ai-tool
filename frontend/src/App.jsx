import "./App.css";
import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";

const API_BASE = "http://127.0.0.1:8000";

function WaveformPlayer({ audioUrl, isActive, onPlayRequest }) {
  const waveformRef = useRef(null);
  const wavesurferRef = useRef(null);
  const [isReady, setIsReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    if (!waveformRef.current) return;

    const ws = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: "#7c8aa5",
      progressColor: "#4f7cff",
      cursorColor: "#222",
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 80,
      responsive: true,
      normalize: true,
    });

    wavesurferRef.current = ws;
    setIsReady(false);
    setIsPlaying(false);

    ws.load(audioUrl);

    ws.on("ready", () => {
      setIsReady(true);
    });

    ws.on("play", () => {
      setIsPlaying(true);
    });

    ws.on("pause", () => {
      setIsPlaying(false);
    });

    ws.on("finish", () => {
      setIsPlaying(false);
    });

    return () => {
      ws.destroy();
    };
  }, [audioUrl]);

  useEffect(() => {
    if (!isActive && wavesurferRef.current?.isPlaying()) {
      wavesurferRef.current.pause();
    }
  }, [isActive]);

  const handleTogglePlay = () => {
    if (!wavesurferRef.current || !isReady) return;

    if (!isPlaying && onPlayRequest) {
      onPlayRequest();
    }

    wavesurferRef.current.playPause();
  };

  return (
    <div className="waveform-player">
      <div className="waveform" ref={waveformRef}></div>
      <button onClick={handleTogglePlay} disabled={!isReady}>
        {!isReady ? "Loading..." : isPlaying ? "Pause" : "Play"}
      </button>
    </div>
  );
}

function AudioItem({
  file,
  index,
  layerOptions,
  onSave,
  onApplyLayer,
  onDelete,
  isActive,
  onPlayRequest,
  isSaving,
  isLayering,
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

  useEffect(() => {
    if (!category) return;

    const subTypes = layerOptions[category] || [];
    if (subTypes.length > 0) {
      setSubType(subTypes[0]);
    } else {
      setSubType("");
    }
  }, [category, layerOptions]);

  const handleLayer = async () => {
    if (!category || !subType) {
      alert("레이어 카테고리와 타입을 선택해줘.");
      return;
    }

    await onApplyLayer(file.filename, category, subType, layerGain, positionMs);
  };

  return (
    <div className="audio-item">
      <div className="audio-header">
        <div className="audio-title-wrap">
          <strong>
            {file.type === "layered" ? "Layered Result" : `Variation ${index + 1}`}
          </strong>
          <span>{file.filename}</span>
        </div>

        <button className="delete-btn" onClick={() => onDelete(file.filename)}>
          Delete
        </button>
      </div>

      <WaveformPlayer
        audioUrl={file.preview_url}
        isActive={isActive}
        onPlayRequest={onPlayRequest}
      />

      <div className="audio-actions">
        <button onClick={() => onSave(file.filename)} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save"}
        </button>

        <a href={`${API_BASE}/download/${file.filename}`} download>
          <button>Download</button>
        </a>
      </div>

      <div className="layer-panel">
        <h4>Layer Options</h4>

        <div className="layer-row">
          <label>Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {categoryKeys.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </div>

        <div className="layer-row">
          <label>Type</label>
          <select
            value={subType}
            onChange={(e) => setSubType(e.target.value)}
          >
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

        <button onClick={handleLayer} disabled={isLayering}>
          {isLayering ? "Layering..." : "Apply Layer"}
        </button>
      </div>
    </div>
  );
}

function App() {
  const [count, setCount] = useState(10);
  const [message, setMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [files, setFiles] = useState([]);
  const [layerOptions, setLayerOptions] = useState({});

  const [isGenerating, setIsGenerating] = useState(false);
  const [savingMap, setSavingMap] = useState({});
  const [layeringMap, setLayeringMap] = useState({});
  const [activePlayer, setActivePlayer] = useState(null);

  useEffect(() => {
    fetchLayerOptions();
  }, []);

  const fetchLayerOptions = async () => {
    try {
      const response = await fetch(`${API_BASE}/layer-options`);
      const data = await response.json();
      setLayerOptions(data.options || {});
    } catch (error) {
      console.error("레이어 옵션 불러오기 실패:", error);
    }
  };

  const handleGenerate = async () => {
    if (!selectedFile) {
      setMessage("먼저 WAV 파일을 선택해줘.");
      return;
    }

    setIsGenerating(true);
    setMessage("생성 중...");
    setFiles([]);
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

      setFiles(data.files || []);
      setMessage(`생성 완료: ${data.files.length}개`);
    } catch (error) {
      setMessage(`에러 발생: ${error.message}`);
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

      alert(`${filename} 저장 완료`);
    } catch (error) {
      alert(`저장 에러: ${error.message}`);
    } finally {
      setSavingMap((prev) => ({ ...prev, [filename]: false }));
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

      setFiles((prev) => [data, ...prev]);
      setMessage(
        `레이어 적용 완료: ${category} / ${subType} / gain ${layerGain}dB / ${positionMs}ms`
      );
    } catch (error) {
      alert(`레이어 에러: ${error.message}`);
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

      if (activePlayer === filename) {
        setActivePlayer(null);
      }
    } catch (error) {
      alert(`삭제 에러: ${error.message}`);
    }
  };

  return (
    <div className="app">
      <h1>Sound AI Tool</h1>
      <p>
        생성 후 미리 들어보고 마음에 드는 variation만 저장하세요.
        이제 파형 확인과 레이어 합성도 가능합니다.
      </p>

      <div className="card">
        <label>WAV 파일 선택</label>
        <input
          type="file"
          accept=".wav"
          onChange={(e) => setSelectedFile(e.target.files[0])}
        />

        <div className="selected-file">
          선택한 파일: {selectedFile ? selectedFile.name : "없음"}
        </div>

        <label>생성 개수</label>
        <input
          type="number"
          min="1"
          max="20"
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
        />

        <button onClick={handleGenerate} disabled={isGenerating}>
          {isGenerating ? "Generating..." : "Generate"}
        </button>

        <div className="result">{message}</div>
      </div>

      {files.length > 0 && (
        <div className="list">
          <h2>Preview Variations</h2>

          {files.map((file, index) => (
            <AudioItem
              key={file.filename}
              file={file}
              index={index}
              layerOptions={layerOptions}
              onSave={handleSave}
              onApplyLayer={handleApplyLayer}
              onDelete={handleDelete}
              isActive={activePlayer === file.filename}
              onPlayRequest={() => setActivePlayer(file.filename)}
              isSaving={!!savingMap[file.filename]}
              isLayering={!!layeringMap[file.filename]}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default App;