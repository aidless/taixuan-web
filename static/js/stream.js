// static/js/stream.js
// SSE 流式客户端(8 派共享)
// 用法:streamReading(liupai, formData, onChunk, onDone, onError, onStart)

async function streamReading(liupai, formData, onChunk, onDone, onError, onStart) {
  try {
    const resp = await fetch(`/api/v2/liupai/${liupai}/reading_stream`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(formData),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `HTTP ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});

      // SSE 协议:每个 \n\n 分隔一条消息
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        // 单条消息可能多行
        const lines = raw.split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6);
          if (payload === '[DONE]') continue;
          try {
            const data = JSON.parse(payload);
            if (data.type === 'start' && onStart) onStart(data);
            else if (data.type === 'chunk' && onChunk) onChunk(data.text);
            else if (data.type === 'done' && onDone) onDone(data);
            else if (data.type === 'error') throw new Error(data.message || 'stream error');
          } catch (parseErr) {
            if (parseErr.message && parseErr.message.startsWith('STREAM_ERROR')) {
              throw parseErr;
            }
            // JSON 解析错误忽略,继续读下一条
            console.warn('SSE parse error:', parseErr, payload);
          }
        }
      }
    }
  } catch (err) {
    if (onError) onError(err.message || String(err));
  }
}

// 暴露到全局
window.streamReading = streamReading;