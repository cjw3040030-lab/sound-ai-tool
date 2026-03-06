import "./App.css";
import { useState } from "react";

function App() {
  const [count, setCount] = useState(10);
  const [message, setMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [files, setFiles] = useState([]);

  const handleGenerate = async () => {
    if (!selectedFile) {
      setMessage("먼저 WAV 파일을 선택해줘.");
      return;
    }

    setMessage("생성 중...");
    setFiles([]);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("num", count);

      const response = await fetch("http://127.0.0.1:8000/generate", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ? JSON.stringify(data.detail) : "생성 실패");
      }

      setFiles(data.files);
      setMessage(`생성 완료: ${data.files.length}개`);
    } catch (error) {
      setMessage(`에러 발생: ${error.message}`);
    }
  };

  const handleSave = async (filename) => {
    try {
      const response = await fetch(`http://127.0.0.1:8000/save/${filename}`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "저장 실패");
      }

      alert(`${filename} 저장 완료`);
    } catch (error) {
      alert(`저장 에러: ${error.message}`);
    }
  };

  return (
    <div className="app">
      <h1>Sound AI Tool</h1>
      <p>생성 후 미리 들어보고 마음에 드는 variation만 저장하세요.</p>

      <div className="card">
        <label>WAV 파일 선택</label>
        <input
          type="file"
          accept=".wav"
          onChange={(e) => setSelectedFile(e.target.files[0])}
        />

        <label>생성 개수</label>
        <input
          type="number"
          min="1"
          max="20"
          value={count}
          onChange={(e) => setCount(e.target.value)}
        />

        <button onClick={handleGenerate}>Generate</button>
        <div className="result">{message}</div>
      </div>

      {files.length > 0 && (
        <div className="list">
          <h2>Preview Variations</h2>
          {files.map((file, index) => (
            <div className="audio-item" key={file.filename}>
              <div className="audio-header">
                <strong>Variation {index + 1}</strong>
                <span>{file.filename}</span>
              </div>

              <audio controls src={file.preview_url}></audio>

              <div className="audio-actions">
                <button onClick={() => handleSave(file.filename)}>Save</button>
                <a
                  href={`http://127.0.0.1:8000/download/${file.filename}`}
                  download
                >
                  <button>Download</button>
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;