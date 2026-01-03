from app import create_app, db
from app.models import Pergunta
from sqlalchemy import func

app = create_app()

def reclassificar_geral():
    with app.app_context():
        print("\n=== RECLASSIFICADOR DE PERGUNTAS 'GERAL' ===")
        print("Este script vai passar por todas as perguntas da categoria 'Geral'.")
        print("Digite a NOVA categoria ou tecle ENTER para manter 'Geral' (pular).\n")

        # --- MUDANÇA AQUI: Busca perguntas onde a categoria é 'Geral' ---
        perguntas_para_alterar = Pergunta.query.filter(
            func.lower(Pergunta.categoria) == 'geral'
        ).all()

        total = len(perguntas_para_alterar)
        if total == 0:
            print("✅ Nenhuma pergunta na categoria 'Geral' encontrada!")
            return

        print(f"Foram encontradas {total} perguntas na categoria 'Geral'.\n")
        
        ultima_categoria_digitada = "" 
        alteradas = 0

        for i, p in enumerate(perguntas_para_alterar, 1):
            print("-" * 60)
            print(f"Pergunta {i}/{total} (ID: {p.id}):")
            print(f"📝 \"{p.texto}\"") 
            
            # Mostra a opção de repetir a última categoria digitada (agiliza muito!)
            dica = f" [Enter para '{ultima_categoria_digitada}']" if ultima_categoria_digitada else " [Enter para pular]"
            
            nova_cat = input(f"Nova Categoria{dica}: ").strip()

            # Lógica Inteligente de Enter
            if nova_cat == "":
                if ultima_categoria_digitada:
                    nova_cat = ultima_categoria_digitada # Usa a anterior
                else:
                    print("⏭️  Mantida como 'Geral'.")
                    continue # Pula para a próxima sem alterar
            else:
                # Formata (Primeira Maiúscula) e salva como a última digitada
                nova_cat = nova_cat.title()
                ultima_categoria_digitada = nova_cat

            # Só salva se houve mudança real
            if p.categoria != nova_cat:
                p.categoria = nova_cat
                alteradas += 1
                print(f"✅ Alterada para: {nova_cat}")
            else:
                print("⏭️  Sem alteração.")

        # Salva tudo no final
        if alteradas > 0:
            print("-" * 60)
            print(f"💾 Salvando {alteradas} alterações no banco de dados...")
            db.session.commit()
            print("🚀 Concluído!")
        else:
            print("\nNenhuma alteração foi feita.")

if __name__ == "__main__":
    reclassificar_geral()