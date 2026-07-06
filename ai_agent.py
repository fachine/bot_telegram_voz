import os
import httpx
import base64
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
FAISS_INDEX_PATH = os.path.join(OUTPUT_DIR, "faiss_index")

class AIAgent:
    def __init__(self):
        try:
            # Embeddings do OpenRouter
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                print("ERRO CRÍTICO: Nenhuma chave API (OPENROUTER_API_KEY) encontrada no ambiente do agente!")
            else:
                masked_key = api_key[:4] + "*" * (len(api_key) - 4) if len(api_key) > 4 else "***"
                print(f"Chave API OpenRouter encontrada: {masked_key} (Tamanho: {len(api_key)})")
                
            self.api_key = api_key
            self.embeddings = OpenAIEmbeddings(
                openai_api_base="https://openrouter.ai/api/v1",
                openai_api_key=api_key,
                model="openai/text-embedding-3-small"
            )
            
            # Chat model do OpenRouter (precisa ser inicializado antes do MultiQueryRetriever)
            print("Inicializando ChatOpenAI para OpenRouter...")
            self.model = ChatOpenAI(
                openai_api_base="https://openrouter.ai/api/v1",
                openai_api_key=api_key,
                model_name="google/gemini-2.5-flash",
                temperature=0.2
            )
            
            # Carregar o índice FAISS (necessita ter sido criado com embeddings do OpenRouter)
            if os.path.exists(FAISS_INDEX_PATH):
                self.vectorstore = FAISS.load_local(FAISS_INDEX_PATH, self.embeddings, allow_dangerous_deserialization=True)
                base_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 4})
                from langchain.retrievers.multi_query import MultiQueryRetriever
                self.retriever = MultiQueryRetriever.from_llm(retriever=base_retriever, llm=self.model)
                print("MultiQueryRetriever configurado com sucesso!")
            else:
                print("Aviso: Índice FAISS não encontrado. Execute document_loader.py primeiro.")
                self.retriever = None
            
            self.ready = True
            print("AIAgent pronto!")
        except Exception as e:
            print(f"Erro ao inicializar IA: {e}")
            self.ready = False

    async def aask(self, question: str, user_id: str) -> str:
        print(f"Recebendo pergunta (Async) do user {user_id}: {question}")
        if not self.ready:
            return "Desculpe, a IA não está configurada corretamente ou a base de conhecimento não foi processada."
        
        try:
            import analytics
            chat_history = analytics.get_recent_history(user_id)
            
            context = ""
            if self.retriever:
                print("Recuperando contexto com RAG Híbrido/MultiQuery...")
                # 1. Recuperar contexto do FAISS de forma assíncrona
                docs = await self.retriever.ainvoke(question)
                context = "\n\n---\n\n".join([doc.page_content for doc in docs])
            
            # 2. Prompt do sistema
            system_prompt = (
                "Você é um assistente virtual de RH e Operações para um condomínio. "
                "Use os seguintes trechos de contexto recuperados dos POPs (Procedimentos Operacionais Padrão) e documentos internos para responder à pergunta do funcionário. "
                "Se você não souber a resposta ou ela não estiver no contexto, diga que não encontrou a informação nos documentos oficiais. "
                "Sempre responda em português, de forma clara, educada e direta.\n\n"
                f"Contexto dos Documentos:\n{context}\n\n"
                f"{chat_history}"
            )
            
            # 3. Chamar Gemini assincronamente
            print("Chamando modelo Gemini...")
            response = await self.model.ainvoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ])
            print("Resposta recebida!")
            return response.content
        except Exception as e:
            return f"Ocorreu um erro ao processar sua pergunta: {e}"

    def stt(self, audio_file_path: str) -> str:
        """Speech to Text usando OpenRouter (Whisper)."""
        print(f"Iniciando STT para arquivo: {audio_file_path}")
        if not self.api_key:
            print("Erro no STT: OPENROUTER_API_KEY não configurada.")
            return ""
        try:
            with open(audio_file_path, "rb") as f:
                audio_data = f.read()
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
            
            ext = os.path.splitext(audio_file_path)[1].lower().replace(".", "")
            format_type = ext if ext else "mp3"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "openai/whisper-1",
                "input_audio": {
                    "data": base64_audio,
                    "format": format_type
                }
            }
            
            print("Solicitando transcrição ao OpenRouter (Whisper)...")
            r = httpx.post(
                "https://openrouter.ai/api/v1/audio/transcriptions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            r.raise_for_status()
            result = r.json()
            transcription = result.get("text", "")
            print(f"Transcrição concluída: {transcription}")
            return transcription
        except Exception as e:
            print(f"Erro no STT (OpenRouter): {e}")
            return ""

    def tts(self, text: str, output_path: str):
        """Text to Speech usando gTTS (Google Text-to-Speech)."""
        print(f"Iniciando TTS para texto: {text[:50]}...")
        try:
            tts = gTTS(text=text, lang='pt', slow=False)
            tts.save(output_path)
            print(f"Áudio salvo em: {output_path}")
            return True
        except Exception as e:
            print(f"Erro no TTS (gTTS): {e}")
            return False

agent = AIAgent()
