from app import create_app, db
from app.models import Pergunta
from sqlalchemy import or_

app = create_app()

def classificar_interativo():
    with app.app_context():
        print("\n=== CLASSIFICADOR RÁPIDO DE PERGUNTAS ANTIGAS ===")
        print("Digite a categoria para cada pergunta ou tecle ENTER para repetir a anterior.\n")

        # Busca apenas perguntas SEM categoria (Null ou Vazio)
        perguntas_sem_cat = Pergunta.query.filter(
            or_(Pergunta.categoria.is_(None), Pergunta.categoria == '')
        ).all()

        total = len(perguntas_sem_cat)
        if total == 0:
            print("✅ Nenhuma pergunta sem categoria encontrada! Tudo organizado.")
            return

        print(f"Foram encontradas {total} perguntas sem categoria.\n")
        
        ultima_categoria = "Geral" # Categoria padrão inicial
        alteradas = 0

        for i, p in enumerate(perguntas_sem_cat, 1):
            print("-" * 60)
            print(f"Pergunta {i}/{total} (ID: {p.id}):")
            print(f"📝 \"{p.texto}\"") # Ajuste se o nome do campo for 'enunciado' ou 'titulo'
            
            # Pergunta a categoria
            nova_cat = input(f"Categoria [Enter para '{ultima_categoria}']: ").strip()

            if nova_cat == "":
                nova_cat = ultima_categoria
            else:
                # Opcional: Já formata bonitinho (Primeira Maiúscula)
                nova_cat = nova_cat.title() 
                ultima_categoria = nova_cat

            p.categoria = nova_cat
            alteradas += 1
            print(f"✅ Salva como: {nova_cat}")

        # Salva tudo no final
        if alteradas > 0:
            print("-" * 60)
            print("💾 Salvando alterações no banco de dados...")
            db.session.commit()
            print("🚀 Concluído! Todas as perguntas foram classificadas.")

if __name__ == "__main__":
    classificar_interativo()