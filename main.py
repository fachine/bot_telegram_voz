import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import document_loader

# Servidor básico para o Health Check do Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot and Loader are Running")
        
    def log_message(self, format, *args):
        return # Silenciar logs do server de saúde

def run_health_check():
    port = int(os.environ.get("PORT", 7860))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Health Check Server rodando na porta {port}")
    server.serve_forever()

if __name__ == "__main__":
    # 1. Iniciar servidor de saúde UMA ÚNICA VEZ
    threading.Thread(target=run_health_check, daemon=True).start()
    
    # 2. Processar documentos (bloqueia até terminar, mas o health check continua rodando)
    print("Iniciando processamento de documentos...")
    document_loader.process_documents()
    
    # 3. Iniciar o bot do Telegram
    print("Iniciando bot do Telegram...")
    import telegram_bot
    telegram_bot.main()
