import os
import shutil

base_dir = r"c:\Users\andre\Desktop\agente_facilities\FICHAS DIGITAIS CONDOMINIO"

# Definição das novas categorias para os arquivos da raiz
mapping = {
    "CONTRATOS": ["CONTRATO"],
    "FORMULÁRIOS E FICHAS": ["FICHA", "FORMULÁRIO", "CHECKLIST"],
    "MANUAIS E REGRAS": ["MANUAL", "REGULAMENTO"]
}

def organize():
    # Criar diretórios se não existirem
    for folder in mapping.keys():
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"Diretório criado: {folder}")

    # Mover arquivos da raiz para as pastas correspondentes
    for filename in os.listdir(base_dir):
        file_path = os.path.join(base_dir, filename)
        
        # Ignorar pastas
        if os.path.isdir(file_path):
            continue
            
        moved = False
        for folder, keywords in mapping.items():
            for kw in keywords:
                if kw in filename.upper():
                    dest_path = os.path.join(base_dir, folder, filename)
                    shutil.move(file_path, dest_path)
                    print(f"Movido: {filename} -> {folder}")
                    moved = True
                    break
            if moved:
                break

if __name__ == "__main__":
    organize()
