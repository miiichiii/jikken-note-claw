# LMStudio モデル切替ガイド（UI不要 / Terminal運用）

最終更新: 2026-02-18

## 目的
外出先などでLMStudioのUIに触れない状況でも、Terminal経由でモデルを切替・実質Ejectする。

---

## 1) モデル状態を確認
```bash
curl -s http://127.0.0.1:1234/api/v0/models | jq -r '.data[] | "\(.id) \(.state)"'
```

例:
- `openai/gpt-oss-20b loaded`
- `gpt-oss-120b not-loaded`

---

## 2) 120Bを外して20Bに切替（実質Eject）
LMStudioはこの環境では明示的な `unload` APIが使えないため、
**別モデルを1回呼び出すことでロードモデルを切り替える**。

```bash
curl -s http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"openai/gpt-oss-20b",
    "messages":[{"role":"user","content":"switch"}],
    "max_tokens":10
  }' > /dev/null

curl -s http://127.0.0.1:1234/api/v0/models | jq -r '.data[] | "\(.id) \(.state)"'
```

期待結果:
- `openai/gpt-oss-20b loaded`
- `gpt-oss-120b not-loaded`

---

## 3) 70Bに切替（同様）
```bash
curl -s http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"deepseek-r1-distill-llama-70b",
    "messages":[{"role":"user","content":"switch"}],
    "max_tokens":20
  }' > /dev/null

curl -s http://127.0.0.1:1234/api/v0/models | jq -r '.data[] | "\(.id) \(.state)"'
```

---

## 4) 全モデルを実質停止（緊急用）
```bash
pkill -f 'llmworker.js'
```

その後、必要なモデルだけ上記手順で1つロードする。

---

## 5) 運用上の注意
- Telegram安定性優先なら、通常は20Bを使う。
- 120Bは重く、他システム（Telegram/ボット応答）に干渉しやすい。
- 70B/120Bは `max_tokens` を小さくしすぎると、空返答に見えることがあるため注意。

