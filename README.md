# Agente de Facilities - Voz (Gemini) 🏢🎙️

Este projeto é um bot do Telegram inteligente projetado para auxiliar na gestão de condomínios e treinamentos de facilities. Ele utiliza a tecnologia do **Google Gemini 1.5 Flash** para processar perguntas em texto e voz, utilizando uma base de conhecimento baseada em documentos (RAG - Retrieval-Augmented Generation).

## ✨ Funcionalidades

- **Chat Inteligente**: Responde a perguntas sobre POPs (Procedimentos Operacionais Padrão) e documentos internos.
- **Voz para Texto (STT)**: Entende mensagens de áudio enviadas pelo Telegram.
- **Texto para Voz (TTS)**: Responde com áudio gerado automaticamente.
- **Gestão de Documentos**: Navegação por categorias (Limpeza, Manutenção, Segurança, etc.).
- **Treinamentos**: Acesso rápido a links de vídeos e documentos de treinamento.
- **Conversão Automática**: Converte documentos DOCX para PDF para facilitar o download no celular.

## 🛠️ Tecnologias Utilizadas

- **LLM**: Google Gemini 1.5 Flash
- **Embeddings**: Google Gemini (`models/gemini-embedding-001`)
- **Framework**: LangChain
- **Banco Vetorial**: FAISS
- **Voz**: gTTS (Google Text-to-Speech)
- **Bot API**: python-telegram-bot

## 🚀 Como Começar

### 1. Requisitos
- Python 3.9+
- Chave de API do Telegram (obtida com o @BotFather)
- Chave de API do Google AI Studio (Gemini)

### 2. Instalação
```bash
pip install -r requirements.txt
```

### 3. Configuração
Crie um arquivo `.env` na raiz da pasta `telegram_bot`:
```env
TELEGRAM_BOT_TOKEN=seu_token_aqui
GOOGLE_API_KEY=sua_chave_gemini_aqui
```

### 4. Carregamento de Documentos
Coloque seus documentos na pasta `FICHAS DIGITAIS CONDOMINIO` e execute o processador para gerar o índice de busca:
```bash
python document_loader.py
```

### 5. Execução
```bash
python telegram_bot.py
```

## 🔒 Segurança

- As chaves de API são gerenciadas via variáveis de ambiente (`.env`).
- O arquivo `.env` e o banco vetorial local são ignorados pelo Git por padrão para evitar exposição de dados sensíveis.
- Documentos na pasta `data/` são protegidos.

## 📄 Licença

Este projeto é para uso operacional interno.
