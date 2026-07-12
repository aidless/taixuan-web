// static/js/stream.js
// v3.0:支持 reasoning(思考过程)+ content(正文)分别显示,实时统计字数,支持中止
// 用法:streamReading(liupai, formData, callbacks)
//   callbacks = { onStart, onReasoning, onContent, onDone, onError }
//   返回 AbortController,可 .abort() 中止流

function streamReading(liupai, formData, callbacks) {
  const {
    onStart = () => {},
    onReasoning = () => {},
    onContent = () => {},
    onDone = () => {},
    onError = null,
  } = callbacks || {};

  const controller = new AbortController();

  (async () => {
    try {
      const resp = await fetch(`/api/v2/liupai/${liupai}/reading_stream`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(formData),
        signal: controller.signal,
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

        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);

          const lines = raw.split('\n');
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6);
            if (payload === '[DONE]') continue;
            try {
              const data = JSON.parse(payload);
              if (data.type === 'start') onStart(data);
              else if (data.type === 'reasoning') onReasoning(data.text);
              else if (data.type === 'content') onContent(data.text, data.chunk_count || 0);
              else if (data.type === 'done') onDone(data);
              else if (data.type === 'error') throw new Error(data.message || 'stream error');
            } catch (parseErr) {
              if (parseErr.message && parseErr.message.includes('STREAM_ERROR')) {
                throw parseErr;
              }
              console.warn('SSE parse error:', parseErr, payload);
            }
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        // 用户主动中止,不报错
        return;
      }
      if (onError) onError(err.message || String(err));
    }
  })();

  // 返回 controller,用户可调用 controller.abort() 中止
  return controller;
}

window.streamReading = streamReading;