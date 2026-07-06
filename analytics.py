import sqlite3
import os
import csv
from datetime import datetime

DB_PATH = "data/analytics.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT,
            question TEXT,
            answer TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_interaction(user_id, question, answer):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_logs (user_id, question, answer) VALUES (?, ?, ?)",
            (str(user_id), question, answer)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar analytics: {e}")

def get_recent_history(user_id, limit=4):
    """
    Retorna as últimas mensagens do usuário formatadas como string
    para injetar como contexto (memória) no RAG.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Busca as ultimas mensagens e ordena cronologicamente
        cursor.execute(
            "SELECT question, answer FROM chat_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (str(user_id), limit)
        )
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return ""
        
        history = "Histórico Recente da Conversa (Contexto):\n"
        # As linhas vêm do mais recente pro mais antigo, vamos inverter para cronológico
        for row in reversed(rows):
            history += f"Usuário: {row[0]}\nBot: {row[1]}\n"
        return history + "\n"
    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
        return ""

def export_metrics():
    """
    Exporta os dados para um CSV temporário e gera estatísticas básicas.
    Retorna (caminho_csv, resumo_texto)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Estatísticas Básicas
        cursor.execute("SELECT COUNT(*) FROM chat_logs")
        total_msg = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM chat_logs")
        total_users = cursor.fetchone()[0]
        
        # Exportar CSV
        csv_path = "data/metricas.csv"
        cursor.execute("SELECT timestamp, user_id, question, answer FROM chat_logs ORDER BY timestamp DESC LIMIT 500")
        rows = cursor.fetchall()
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "User ID", "Pergunta", "Resposta"])
            writer.writerows(rows)
            
        conn.close()
        
        resumo = f"📊 *Resumo de Uso:*\n- Total de Interações: {total_msg}\n- Usuários Únicos: {total_users}\n(Mostrando os 500 registros mais recentes no CSV)"
        return csv_path, resumo
    except Exception as e:
        print(f"Erro ao exportar métricas: {e}")
        return None, f"Erro ao gerar métricas: {str(e)}"
