from app import app, db, Administrador

with app.app_context():
    # 1. Cria a tabela no banco (se não existir)
    db.create_all()
    
    # 2. Verifica se já existe algum admin
    if not Administrador.query.first():
        print("Criando o administrador mestre...")
        
        # Defina aqui os dados do seu primeiro admin
        admin = Administrador(nome="Super Admin", email="jenycds@hotmail.com")
        admin.set_senha("admin123") # Essa será a senha de acesso
        
        db.session.add(admin)
        db.session.commit()
        print(f"Admin criado com sucesso! Login: {admin.email} | Senha: admin123")
    else:
        print("Já existem administradores cadastrados.")