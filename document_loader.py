import os
import glob
import json
import platform
import subprocess
from docx2pdf import convert
from langchain_community.document_loaders import Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()

# Caminhos configuráveis (ajusta automaticamente entre Windows local e Linux servidor)
BASE_DIR = os.getenv("DOCS_PATH", r"c:\Users\andre\Desktop\agente_facilities\telegram_bot\FICHAS DIGITAIS CONDOMINIO")
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

def process_documents():
    init_dirs()
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
        
        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.from_documents(splits, embeddings)
        vectorstore.save_local(os.path.join(OUTPUT_DIR, "faiss_index"))
        print("VectorStore salvo com sucesso!")
    else:
        print("Nenhum documento processado para o VectorStore.")

if __name__ == "__main__":
    process_documents()
