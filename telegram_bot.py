import os
import json
import logging
import docx2txt
import threading
import httpx
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ApplicationBuilder
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
import socket
import urllib.request

# Carregar variáveis de ambiente
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar estrutura do menu gerada pelo document_loader.py
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
MENU_FILE = os.path.join(OUTPUT_DIR, "menu_structure.json")

def load_menu():
    try:
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar menu: {e}")
        return {}

MENU_DATA = load_menu()

# Tentar importar o AIAgent, mas o bot não deve quebrar se falhar
try:
    from ai_agent import agent
except ImportError:
    logger.error("Erro ao importar AIAgent. Certifique-se de que o FAISS Index foi gerado.")
    agent = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    welcome_message = (
        "Olá! Sou o Assistente Virtual do Condomínio. 🏢\n\n"
        "Posso te ajudar a encontrar documentos e Treinamentos.\n"
        "Escolha uma opção abaixo ou digite sua pergunta:"
    )
    
    keyboard = []
    # Categorias normais (que não são treinamentos)
    for category in sorted(MENU_DATA.keys()):
        if not category.startswith("TREINAMENTOS"):
            keyboard.append([InlineKeyboardButton(f"📂 {category}", callback_data=f"cat_{category}")])
    
    # Adicionar o botão de TREINAMENTOS se houver algo neles
    has_trainings = any(c.startswith("TREINAMENTOS") for c in MENU_DATA.keys())
    if has_trainings:
        keyboard.append([InlineKeyboardButton("🎓 TREINAMENTOS", callback_data="train_menu")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Sistema de retentativa para lidar com a rede instável do Hugging Face
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if update.message:
                await update.message.reply_text(welcome_message, reply_markup=reply_markup)
            else:
                await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup)
            return # Sucesso!
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Falha definitiva ao enviar mensagem de boas-vindas: {e}")
            else:
                logger.warning(f"Tentativa {attempt+1} falhou, tentando novamente em 1s...")
                await asyncio.sleep(1)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "main_menu":
        await start(update, context)
        
    elif data == "train_menu":
        keyboard = []
        # Garantir que as 4 áreas principais sempre apareçam
        training_areas = ["LIMPEZA", "MANUTENÇÃO", "SEGURANÇA", "JARDINAGEM"]
        
        for area in training_areas:
            # O callback_data precisa bater com o que o document_loader gera
            category_name = f"TREINAMENTOS - {area}"
            keyboard.append([InlineKeyboardButton(area, callback_data=f"cat_{category_name}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Voltar ao Menu Principal", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="🎓 *Áreas de Treinamento*\n\nSelecione a área desejada:", parse_mode="Markdown", reply_markup=reply_markup)
        
    elif data.startswith("cat_"):
        category = data[4:]
        docs = MENU_DATA.get(category, [])
        keyboard = []
        
        if not docs:
            msg_text = f"Área: *{category}*\n\n📭 Ainda não há arquivos ou treinamentos cadastrados nesta área."
        else:
            # Como o callback_data tem limite de 64 bytes, vamos usar o índice do documento na lista
            for i, doc in enumerate(docs):
                doc_name = doc["name"]
                # Limitar tamanho do nome no botão se for muito grande
                btn_text = doc_name[:40] + "..." if len(doc_name) > 40 else doc_name
                
                # Se for vídeo, o botão abre o link diretamente
                if doc.get("type") == "video":
                    keyboard.append([InlineKeyboardButton(f"▶️ {btn_text}", url=doc.get("url", ""))])
                else:
                    keyboard.append([InlineKeyboardButton(f"📄 {btn_text}", callback_data=f"doc_{category}_{i}")])
            
            msg_text = f"Área: *{category}*\n\nSelecione um documento:"
            if "TREINAMENTO" in category.upper():
                msg_text = f"Área: *{category}*\n\nSelecione um treinamento em vídeo:"
            
        back_callback = "main_menu"
        if category.startswith("TREINAMENTOS"):
            back_callback = "train_menu"
            
        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data=back_callback)])
        reply_markup = InlineKeyboardMarkup(keyboard)
            
        await query.edit_message_text(text=msg_text, parse_mode="Markdown", reply_markup=reply_markup)
        
    elif data.startswith("doc_"):
        parts = data.split("_", 2)
        if len(parts) == 3:
            category = parts[1]
            doc_index = int(parts[2])
            doc = MENU_DATA.get(category, [])[doc_index]
            
            doc_name = doc["name"]
            pdf_path = doc["pdf_path"]
            
            text = f"📄 *{doc_name}*\n\nO que você deseja fazer?"
            keyboard = [
                [InlineKeyboardButton("📖 Ler no Chat (Resumo IA)", callback_data=f"read_{category}_{doc_index}")],
                [InlineKeyboardButton("📥 Baixar Documento (PDF)", callback_data=f"dl_{category}_{doc_index}")],
                [InlineKeyboardButton("🔙 Voltar", callback_data=f"cat_{category}")],
                [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=reply_markup)
            
    elif data.startswith("dl_"):
        parts = data.split("_", 2)
        if len(parts) == 3:
            category = parts[1]
            doc_index = int(parts[2])
            doc = MENU_DATA.get(category, [])[doc_index]
            
            # Reconstruir caminho absoluto para o servidor
            rel_pdf_path = doc["pdf_path"]
            abs_pdf_path = os.path.join(os.path.dirname(__file__), rel_pdf_path)
            
            if os.path.exists(abs_pdf_path):
                # Se for arquivo .txt (fallback de falha de pdf), manda como documento também
                await context.bot.send_document(chat_id=query.message.chat_id, document=open(abs_pdf_path, 'rb'))
            else:
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Desculpe, o arquivo não foi encontrado no servidor.")

    elif data.startswith("read_"):
        parts = data.split("_", 2)
        if len(parts) == 3:
            category = parts[1]
            doc_index = int(parts[2])
            doc = MENU_DATA.get(category, [])[doc_index]
            
            # Reconstruir caminho absoluto para o servidor
            rel_docx_path = doc.get("docx_path")
            abs_docx_path = os.path.join(os.path.dirname(__file__), rel_docx_path) if rel_docx_path else None
            
            if abs_docx_path and os.path.exists(abs_docx_path):
                await query.edit_message_text(text=f"⏳ Lendo *{doc['name']}* e preparando resumo...", parse_mode="Markdown")
                
                try:
                    # Extrair texto
                    content = docx2txt.process(abs_docx_path)
                    
                    if agent and agent.ready:
                        # Usar a IA para fazer um resumo estruturado
                        prompt = f"Por favor, faça um resumo estruturado e fácil de ler (em bullet points) do seguinte documento operacional: \n\n{content[:4000]}"
                        summary = agent.ask(prompt)
                        
                        keyboard = [[InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await query.edit_message_text(
                            text=f"📋 *Resumo: {doc['name']}*\n\n{summary}",
                            parse_mode="Markdown",
                            reply_markup=reply_markup
                        )
                    else:
                        # Fallback se a IA falhar: manda os primeiros 1000 caracteres
                        preview = content[:1000] + "..." if len(content) > 1000 else content
                        await query.edit_message_text(text=f"📄 *Conteúdo de {doc['name']}:*\n\n{preview}", parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Erro ao ler documento: {e}")
                    await query.edit_message_text(text="❌ Erro ao tentar ler o conteúdo do documento.")
            else:
                await query.edit_message_text(text="❌ Arquivo original não encontrado.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle generic text messages using AI."""
    text = update.message.text.lower().strip()
    
    # Lista de gatilhos para o menu inicial (pode estar no meio da mensagem)
    menu_triggers = ["menu", "inicio", "início", "ajuda", "voltar", "oi", "olá", "ola", "voltar ao menu", "menu inicial"]
    
    if any(trigger in text for trigger in menu_triggers):
        await start(update, context)
        return

    # Notifica o usuário que está pensando
    waiting_msg = await update.message.reply_text("🤔 Buscando na base de conhecimento...")
    
    if agent and agent.ready:
        answer = agent.ask(update.message.text)
        await waiting_msg.edit_text(answer)
    else:
        await waiting_msg.edit_text("❌ Desculpe, a Inteligência Artificial ainda não está configurada ou a base de dados não foi carregada.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages: STT -> Agent -> TTS."""
    voice = update.message.voice
    
    # Criar pasta temp se não existir
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Notifica o usuário
    status_msg = await update.message.reply_text("🎤 Ouvindo seu áudio...")
    
    try:
        # 1. Download do áudio (.ogg)
        file = await context.bot.get_file(voice.file_id)
        input_path = os.path.join(temp_dir, f"voice_{voice.file_id}.ogg")
        await file.download_to_drive(input_path)
        
        if agent and agent.ready:
            # 2. Transcrição (STT)
            await status_msg.edit_text("✍️ Transcrevendo áudio...")
            transcription = agent.stt(input_path)
            
            if not transcription:
                await status_msg.edit_text("❌ Não consegui entender o áudio. Por favor, tente falar mais claro ou digite sua pergunta.")
                return

            # 3. Processar pergunta (RAG)
            await status_msg.edit_text(f"🔍 Buscando resposta...")
            answer = agent.ask(transcription)
            
            # Enviar a resposta em texto primeiro (garante que o usuário receba a informação)
            await update.message.reply_text(f"📝 *Resposta:* \n\n{answer}", parse_mode="Markdown")

            # 4. Síntese de Voz (TTS)
            await status_msg.edit_text("🗣️ Gerando resposta em áudio...")
            output_path = os.path.join(temp_dir, f"reply_{voice.file_id}.mp3")
            
            print(f"Tentando gerar áudio TTS em: {output_path}")
            success = agent.tts(answer, output_path)
            
            if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                # Enviar áudio de volta
                print(f"Enviando áudio de volta para o usuário... Tamanho: {os.path.getsize(output_path)} bytes")
                with open(output_path, "rb") as audio_file:
                    await update.message.reply_voice(voice=audio_file, caption="Ouça a resposta acima 👆")
                await status_msg.delete()
            else:
                print(f"Falha no TTS ou arquivo vazio. Sucesso: {success}")
                await status_msg.edit_text("⚠️ Não consegui gerar o áudio, mas enviei a resposta em texto acima.")
            
            # Limpeza de arquivos temporários
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_path): os.remove(output_path)
            
        else:
            await status_msg.edit_text("❌ A Inteligência Artificial não está disponível no momento.")
            
    except Exception as e:
        logger.error(f"Erro ao processar voz: {e}")
        await status_msg.edit_text(f"❌ Ocorreu um erro ao processar seu áudio.")

async def post_init(application: Application) -> None:
    """Set bot commands in the UI menu."""
    commands = [
        ("start", "Iniciar o bot e ver o menu principal"),
        ("menu", "Exibir o menu de categorias"),
        ("ajuda", "Ver instruções de uso")
    ]
    await application.bot.set_my_commands(commands)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error(f"Exceção capturada pelo manipulador de erros: {context.error}")
    # Se for erro de rede, apenas ignoramos pois o polling vai tentar de novo
    if "httpx.ConnectError" in str(context.error) or "Timed out" in str(context.error):
        logger.warning("Erro de rede detectado. O bot continuará tentando...")
        return

# Servidor básico para o Health Check do Hugging Face
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running")

    def log_message(self, format, *args):
        return # Silenciar logs do server de saúde

def run_health_check():
    port = int(os.environ.get("PORT", 7860))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Health Check Server rodando na porta {port}")
    server.serve_forever()

def check_network():
    """Verifica a conectividade básica usando múltiplos métodos."""
    targets = ["api.telegram.org", "www.google.com", "generativelanguage.googleapis.com"]
    
    for target in targets:
        # Teste 1: DNS (Resolução de nome)
        try:
            ip = socket.gethostbyname(target)
            logger.info(f"DNS {target} OK: IP {ip}")
        except Exception as e:
            logger.error(f"DNS {target} FALHOU: {e}")
            
        # Teste 2: Conectividade básica (Socket)
        try:
            s = socket.create_connection((target, 443), timeout=10)
            logger.info(f"Porta 443 {target} está ABERTA (Socket OK)")
            s.close()
        except Exception as e:
            logger.error(f"Porta 443 {target} está FECHADA ou TIME-OUT: {e}")

        # Teste 3: HTTP Simples (urllib)
        try:
            url = f"https://{target}"
            with urllib.request.urlopen(url, timeout=20) as response:
                logger.info(f"HTTP {target} OK! Status: {response.getcode()}")
        except Exception as e:
            logger.error(f"HTTP {target} FALHOU: {e}")

    return {}

def main() -> None:
    """Start the bot."""
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não encontrado. Verifique o arquivo .env.")
        return

    # Iniciar servidor de saúde em uma thread separada para o Hugging Face
    threading.Thread(target=run_health_check, daemon=True).start()

    # Diagnóstico inicial de rede
    check_network()

    # Configuração de rede ultra-robusta para evitar Timeouts no Hugging Face
    request_config = HTTPXRequest(
        connection_pool_size=10, # Reduzido para evitar bloqueio de socket no HF
        read_timeout=120.0,
        write_timeout=120.0,
        connect_timeout=120.0,
        pool_timeout=120.0
    )

    application = (
        Application.builder()
        .token(TOKEN)
        .request(request_config)
        .post_init(post_init)
        .build()
    )

    # Registrar manipulador de erros global
    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("ajuda", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    print("Bot do Telegram Iniciado com sucesso! Pressione Ctrl+C para parar.")
    
    # Loop de retry para o caso de o bot cair por erro de rede (comum no Hugging Face)
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                bootstrap_retries=-1 # Tentativas infinitas na inicialização interna
            )
            # Se run_polling terminar normalmente (sem exceção), saímos do loop
            break
        except Exception as e:
            retry_count += 1
            logger.error(f"Erro crítico no polling (Tentativa {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                wait_time = min(5 * retry_count, 60) # Backoff progressivo até 60s
                logger.info(f"Reiniciando polling em {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.critical("Limite de retentativas atingido. O bot parou.")

if __name__ == "__main__":
    main()
