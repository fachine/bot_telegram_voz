import os
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

# Configuração do Google GenAI SDK (necessário para STT multimodal)
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
FAISS_INDEX_PATH = os.path.join(OUTPUT_DIR, "faiss_index")

class AIAgent:
    def __init__(self):
        try:
            # Embeddings do Google
            self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
            
            # Carregar o índice FAISS (necessita ter sido criado com embeddings do Google)
            if os.path.exists(FAISS_INDEX_PATH):
                self.vectorstore = FAISS.load_local(FAISS_INDEX_PATH, self.embeddings, allow_dangerous_deserialization=True)
                self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 4})
            else:
                print("Aviso: Índice FAISS não encontrado. Execute document_loader.py primeiro.")
                self.retriever = None
            
            # Chat model do Google
            self.model = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=0.2,
                google_api_key=os.getenv("GOOGLE_API_KEY")
            )
            
            # Modelo para STT (usando o SDK direto do Google)
            self.genai_model = genai.GenerativeModel("gemini-1.5-flash")
            
            self.ready = True
        except Exception as e:
            print(f"Erro ao inicializar IA: {e}")
            self.ready = False

    def ask(self, question: str) -> str:
        if not self.ready:
            return "Desculpe, a IA não está configurada corretamente ou a base de conhecimento não foi processada."
        
        try:
            context = ""
            if self.retriever:
                # 1. Recuperar contexto do FAISS
                docs = self.retriever.invoke(question)
                context = "\n\n---\n\n".join([doc.page_content for doc in docs])
            
            # 2. Prompt do sistema
            system_prompt = (
                "Você é um assistente virtual de RH e Operações para um condomínio. "
                "Use os seguintes trechos de contexto recuperados dos POPs (Procedimentos Operacionais Padrão) e documentos internos para responder à pergunta do funcionário. "
                "Se você não souber a resposta ou ela não estiver no contexto, diga que não encontrou a informação nos documentos oficiais. "
                "Sempre responda em português, de forma clara, educada e direta.\n\n"
                f"Contexto:\n{context}"
            )
            
            # 3. Chamar Gemini
            response = self.model.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ])
            
            return response.content
        except Exception as e:
            return f"Ocorreu um erro ao processar sua pergunta: {e}"

    def stt(self, audio_file_path: str) -> str:
        """Speech to Text usando Gemini 1.5 Flash (Multimodal)."""
        try:
            # Upload do arquivo para o Google (temporário)
            audio_file = genai.upload_file(path=audio_file_path)
            
            # Gerar transcrição
            response = self.genai_model.generate_content([
                audio_file, 
                "Por favor, transcreva este áudio exatamente como dito, sem adicionar comentários."
            ])
            
            # Deletar o arquivo do servidor do Google após o uso
            genai.delete_file(audio_file.name)
            
            return response.text
        except Exception as e:
            print(f"Erro no STT (Gemini): {e}")
            return ""

    def tts(self, text: str, output_path: str):
        """Text to Speech usando gTTS (Google Text-to-Speech)."""
        try:
            tts = gTTS(text=text, lang='pt', slow=False)
            tts.save(output_path)
            return True
        except Exception as e:
            print(f"Erro no TTS (gTTS): {e}")
            return False

agent = AIAgent()
