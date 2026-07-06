import os
import glob
import json
import platform
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from docx2pdf import convert
from langchain_community.document_loaders import Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()

# Servidor básico para o Health Check do Render/Hugging Face
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Loader is Running")
    def log_message(self, format, *args):
        return

def run_health_check():
    port = int(os.environ.get("PORT", 7860))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Health Check Server do Loader rodando na porta {port}")
    server.serve_forever()

# Caminhos configuráveis (ajusta automaticamente entre Windows local e Linux servidor)
BASE_DIR = os.getenv("DOCS_PATH", r"c:\Users\andre\Desktop\agente_facilities voz\telegram_bot\FICHAS DIGITAIS CONDOMINIO")
# Se o caminho absoluto não existir (no servidor), tenta o relativo dentro da pasta do bot
if not os.path.exists(BASE_DIR):
    BASE_DIR = os.path.join(os.path.dirname(__file__), "FICHAS DIGITAIS CONDOMINIO")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
PDF_DIR = os.path.join(OUTPUT_DIR, "pdfs")

def init_dirs():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    if not os.path.exists(PDF_DIR):
        os.makedirs(PDF_DIR)

def process_documents(force=False):
    init_dirs()
    index_path = os.path.join(OUTPUT_DIR, "faiss_index")
    if not force and os.path.exists(os.path.join(index_path, "index.faiss")):
        print(f"Índice FAISS já existe em {index_path}. Pulando processamento. Use /atualizardocs para forçar.")
        return

    print("Iniciando processamento de documentos...")
    
    docs = []
    
    # Mapeamento de categorias e arquivos para o bot
    menu_structure = {}
    
    # Encontrar todos os docx e txt
    files_to_process = glob.glob(os.path.join(BASE_DIR, "**", "*.docx"), recursive=True)
    files_to_process += glob.glob(os.path.join(BASE_DIR, "**", "*.txt"), recursive=True)
    
    for file_path in files_to_process:
        try:
            filename = os.path.basename(file_path)
            ext = os.path.splitext(filename)[1].lower()
            
            # Descobrir categoria (nome da pasta pai ou "GERAL" se estiver na raiz)
            parent_path = os.path.dirname(file_path)
            parent_dir = os.path.basename(parent_path)
            grandparent_dir = os.path.basename(os.path.dirname(parent_path))
            
            if grandparent_dir.upper() == "TREINAMENTOS":
                category = f"TREINAMENTOS - {parent_dir.upper()}"
            elif parent_dir.upper() == "TREINAMENTOS":
                 category = "TREINAMENTOS"
            elif parent_dir.upper() in ["FICHAS DIGITAIS CONDOMINIO", "POPS (PROCEDIMENTOS OPERACIONAIS PADRAO)", "FICHAS DIGITAIS"]:
                category = "GERAL"
            else:
                category = parent_dir.upper()
                
            if category not in menu_structure:
                menu_structure[category] = []
                
            # Registrar na estrutura do menu
            item_data = {
                "name": filename.replace(ext, ""),
                "type": "doc"
            }

            if ext == ".docx":
                pdf_filename = filename.replace(".docx", ".pdf")
                pdf_path = os.path.join(PDF_DIR, pdf_filename)
                
                # Converter para PDF se ainda não existir
                if not os.path.exists(pdf_path):
                    print(f"Convertendo para PDF: {filename}")
                    try:
                        if platform.system() == "Windows":
                            convert(file_path, pdf_path)
                        else:
                            # Comando para Linux (LibreOffice)
                            subprocess.run([
                                'libreoffice', '--headless', '--convert-to', 'pdf',
                                '--outdir', PDF_DIR, file_path
                            ], check=True)
                    except Exception as e:
                        print(f"Erro na conversão para PDF de {filename}: {e}")
                
                item_data.update({
                    "pdf_path": os.path.relpath(pdf_path, os.path.dirname(__file__)),
                    "docx_path": os.path.relpath(file_path, os.path.dirname(__file__))
                })
                
                # Carregar texto para a base vetorial
                loader = Docx2txtLoader(file_path)
                doc_data = loader.load()
                for d in doc_data:
                    d.metadata["source"] = filename
                    d.metadata["category"] = category
                    docs.append(d)
            
            elif ext == ".txt":
                # Se for TXT, assumimos que é um link de vídeo
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    url = ""
                    for line in lines:
                        clean_line = line.strip()
                        if clean_line.startswith("http"):
                            url = clean_line
                            break
                
                item_data.update({
                    "type": "video",
                    "url": url
                })

            menu_structure[category].append(item_data)
                
        except Exception as e:
            print(f"Erro ao processar arquivo {file_path}: {e}")
            
    # Salvar estrutura de menu em JSON
    with open(os.path.join(OUTPUT_DIR, "menu_structure.json"), "w", encoding="utf-8") as f:
        json.dump(menu_structure, f, ensure_ascii=False, indent=4)
        
    if len(docs) > 0:
        print(f"Criando VectorStore com {len(docs)} documentos base...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("ERRO CRÍTICO: Nenhuma chave API (OPENROUTER_API_KEY) encontrada no ambiente!")
        else:
            masked_key = api_key[:4] + "*" * (len(api_key) - 4) if len(api_key) > 4 else "***"
            print(f"Chave API OpenRouter encontrada: {masked_key} (Tamanho: {len(api_key)})")
            
        embeddings = OpenAIEmbeddings(
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=api_key,
            model="openai/text-embedding-3-small"
        )
        
        # Processar em lotes moderados para evitar erro 429 (RESOURCE_EXHAUSTED)
        batch_size = 10
        vectorstore = None
        
        print(f"Processando {len(splits)} chunks em lotes de {batch_size}...")
        i = 0
        while i < len(splits):
            batch = splits[i:i + batch_size]
            try:
                if vectorstore is None:
                    vectorstore = FAISS.from_documents(batch, embeddings)
                else:
                    vectorstore.add_documents(batch)
                
                print(f"Lote {i//batch_size + 1}/{(len(splits)-1)//batch_size + 1} concluído.")
                i += batch_size
                import time
                time.sleep(5) # Espera 5 segundos entre lotes
            except Exception as e:
                if "429" in str(e):
                    print("Limite atingido (429), esperando 60 segundos...")
                    import time
                    time.sleep(60)
                else:
                    raise e
            
        vectorstore.save_local(os.path.join(OUTPUT_DIR, "faiss_index"))
        print("VectorStore salvo com sucesso!")
    else:
        print("Nenhum documento processado para o VectorStore.")

if __name__ == "__main__":
    # Iniciar servidor de saúde em uma thread separada para o Render não dar timeout
    threading.Thread(target=run_health_check, daemon=True).start()
    process_documents()
