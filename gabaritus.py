import sqlite3
import os
from datetime import datetime
from kivy.utils import platform

class Database:
    def __init__(self, db_name="gabaritus_v3.db"):
        """Inicializa o banco de dados e cria as tabelas necessárias"""
        # Define o caminho correto para cada plataforma
        if platform == 'android':
            # No Android, usa o diretório de documentos
            from android.storage import primary_external_storage_path
            base_path = primary_external_storage_path()
            self.db_path = os.path.join(base_path, "Documents", "Gabaritus_backup", db_name)
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        else:
            # No desktop, usa o diretório local
            self.db_path = db_name
        
        self.conn = sqlite3.connect(self.db_path)
        
        # ⭐⭐⭐ ATIVAÇÃO CRÍTICA DAS CHAVES ESTRANGEIRAS ⭐⭐⭐
        # SQLite mantém FOREIGN KEYS desativado por padrão
        # Esta linha é ESSENCIAL para o CASCADE funcionar!
        self.conn.execute("PRAGMA foreign_keys = ON")
        
        # Verifica se ativou corretamente
        resultado = self.conn.execute("PRAGMA foreign_keys").fetchone()
        if resultado and resultado[0] == 1:
            print("✅ Chaves estrangeiras ativadas com sucesso!")
        else:
            print("⚠️ ATENÇÃO: Falha ao ativar chaves estrangeiras!")
        
        self.conn.row_factory = sqlite3.Row  # Permite acesso por nome de coluna
        self.criar_tabelas()
        self.inicializar_senha_padrao()
        self.atualizar_tabela_presencas()  # Adiciona campo trimestre se necessário
    
    def criar_tabelas(self):
        """Cria todas as tabelas necessárias para o sistema"""
        cursor = self.conn.cursor()
        
        # Tabela de configuração (senha, etc)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY,
                senha TEXT NOT NULL,
                ultimo_backup TEXT
            )
        ''')

        # Tabela para o Calendário Letivo
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendario (
                id INTEGER PRIMARY KEY,
                tri1_inicio TEXT, tri1_fim TEXT,
                tri2_inicio TEXT, tri2_fim TEXT,
                tri3_inicio TEXT, tri3_fim TEXT
            )
        ''')
        
        # Tabela do professor
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS professor (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                materia TEXT NOT NULL,
                esfera TEXT,
                instituicao TEXT NOT NULL,
                secretaria TEXT,
                email TEXT,
                telefone TEXT
            )
        ''')
        
        # Tabela de disciplinas (matérias)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS disciplinas (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL UNIQUE,
                data_criacao TEXT DEFAULT CURRENT_TIMESTAMP,
                ativo INTEGER DEFAULT 1
            )
        ''')
        
        # Tabela de turmas (vinculada à disciplina)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS turmas (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                disciplina_id INTEGER,
                data_criacao TEXT DEFAULT CURRENT_TIMESTAMP,
                ativo INTEGER DEFAULT 1,
                FOREIGN KEY (disciplina_id) REFERENCES disciplinas (id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de alunos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alunos (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                turma_id INTEGER,
                matricula TEXT,
                data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP,
                ativo INTEGER DEFAULT 1,
                FOREIGN KEY (turma_id) REFERENCES turmas (id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de atividades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS atividades (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                turma_id INTEGER,
                valor REAL DEFAULT 10.0,
                trimestre INTEGER DEFAULT 1,
                tipo TEXT DEFAULT 'normal',
                data_criacao TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (turma_id) REFERENCES turmas (id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de notas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notas (
                id INTEGER PRIMARY KEY,
                aluno_id INTEGER,
                atividade_id INTEGER,
                nota REAL DEFAULT 0,
                data_lancamento TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (aluno_id) REFERENCES alunos (id) ON DELETE CASCADE,
                FOREIGN KEY (atividade_id) REFERENCES atividades (id) ON DELETE CASCADE,
                UNIQUE(aluno_id, atividade_id)
            )
        ''')
        
        # Tabela de presenças (chamada) - VERSÃO ATUALIZADA COM TRIMESTRE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS presencas (
                id INTEGER PRIMARY KEY,
                aluno_id INTEGER,
                turma_id INTEGER,
                data TEXT NOT NULL,
                tema TEXT,
                status INTEGER DEFAULT 1,
                justificativa TEXT,
                trimestre INTEGER,
                FOREIGN KEY (aluno_id) REFERENCES alunos (id) ON DELETE CASCADE,
                FOREIGN KEY (turma_id) REFERENCES turmas (id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de ocorrências (diário de bordo)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ocorrencias (
                id INTEGER PRIMARY KEY,
                aluno_id INTEGER,
                categoria TEXT,
                texto TEXT NOT NULL,
                data_hora TEXT DEFAULT CURRENT_TIMESTAMP,
                trimestre INTEGER,
                FOREIGN KEY (aluno_id) REFERENCES alunos (id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de backup dos gabaritos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gabaritos (
                id INTEGER PRIMARY KEY,
                atividade_id INTEGER,
                versao TEXT,
                respostas TEXT,
                data_criacao TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (atividade_id) REFERENCES atividades (id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de planejamento
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS planejamento (
                id INTEGER PRIMARY KEY,
                turma_id INTEGER,
                data_aula TEXT,
                titulo TEXT NOT NULL,
                conteudo TEXT,
                objetivos TEXT,
                metodologia TEXT,
                trimestre INTEGER,
                status INTEGER DEFAULT 0,
                FOREIGN KEY (turma_id) REFERENCES turmas (id) ON DELETE CASCADE
            )
        ''')
        
        self.conn.commit()
    
    def atualizar_tabela_presencas(self):
        """Adiciona campo trimestre à tabela presencas se não existir"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("ALTER TABLE presencas ADD COLUMN trimestre INTEGER")
            self.conn.commit()
            print("✅ Campo 'trimestre' adicionado à tabela presencas")
        except sqlite3.OperationalError:
            # Campo já existe
            pass
    
    def inicializar_senha_padrao(self):
        """Define senha padrão 'admin' se não existir"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM config")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO config (senha) VALUES (?)", ("admin",))
            self.conn.commit()

    # ==================== MÉTODOS DE CALENDÁRIO ====================

    def salvar_calendario(self, datas):
        """Salva ou atualiza as datas dos trimestres."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM calendario WHERE id = 1")
        if cursor.fetchone():
            cursor.execute('''
                UPDATE calendario SET 
                tri1_inicio=?, tri1_fim=?, 
                tri2_inicio=?, tri2_fim=?, 
                tri3_inicio=?, tri3_fim=? 
                WHERE id = 1
            ''', datas)
        else:
            cursor.execute('''
                INSERT INTO calendario 
                (id, tri1_inicio, tri1_fim, tri2_inicio, tri2_fim, tri3_inicio, tri3_fim) 
                VALUES (1, ?, ?, ?, ?, ?, ?)
            ''', datas)
        self.conn.commit()

    def buscar_calendario(self):
        """Retorna as datas do calendário letivo"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT tri1_inicio, tri1_fim, tri2_inicio, tri2_fim, tri3_inicio, tri3_fim FROM calendario WHERE id = 1")
        return cursor.fetchone()

    # ==================== MÉTODOS DE AUTENTICAÇÃO ====================
    
    def buscar_senha(self):
        """Retorna a senha atual do sistema"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT senha FROM config LIMIT 1")
        resultado = cursor.fetchone()
        return resultado[0] if resultado else "admin"
    
    def atualizar_senha(self, nova_senha):
        """Atualiza a senha do sistema"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE config SET senha = ?", (nova_senha,))
        self.conn.commit()
    
    # ==================== MÉTODOS DO PROFESSOR ====================
    
    def salvar_professor(self, nome, materia, esfera, instituicao, secretaria=""):
        """Salva ou atualiza os dados do professor"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO professor (id, nome, materia, esfera, instituicao, secretaria)
            VALUES (1, ?, ?, ?, ?, ?)
        ''', (nome, materia, esfera, instituicao, secretaria))
        self.conn.commit()
    
    def buscar_professor(self):
        """Retorna os dados do professor como tupla (nome, materia, esfera, instituicao, secretaria)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT nome, materia, esfera, instituicao, secretaria FROM professor WHERE id = 1")
        resultado = cursor.fetchone()
        return resultado if resultado else None
    
    def atualizar_professor(self, nome=None, materia=None, esfera=None, instituicao=None, secretaria=None):
        """Atualiza campos específicos do professor"""
        cursor = self.conn.cursor()
        if nome:
            cursor.execute("UPDATE professor SET nome = ? WHERE id = 1", (nome,))
        if materia:
            cursor.execute("UPDATE professor SET materia = ? WHERE id = 1", (materia,))
        if esfera:
            cursor.execute("UPDATE professor SET esfera = ? WHERE id = 1", (esfera,))
        if instituicao:
            cursor.execute("UPDATE professor SET instituicao = ? WHERE id = 1", (instituicao,))
        if secretaria:
            cursor.execute("UPDATE professor SET secretaria = ? WHERE id = 1", (secretaria,))
        self.conn.commit()
    
    # ==================== MÉTODOS DE DISCIPLINAS ====================
    
    def salvar_disciplina(self, nome):
        """Salva uma nova disciplina"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO disciplinas (nome) VALUES (?)", (nome.upper(),))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
    
    def buscar_disciplinas(self):
        """Retorna todas as disciplinas ativas"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, nome FROM disciplinas WHERE ativo = 1 ORDER BY nome")
        return cursor.fetchall()
    
    def buscar_disciplina_por_id(self, disciplina_id):
        """Retorna uma disciplina específica"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, nome FROM disciplinas WHERE id = ? AND ativo = 1", (disciplina_id,))
        return cursor.fetchone()
    
    def editar_disciplina(self, disciplina_id, novo_nome):
        """Edita o nome de uma disciplina"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE disciplinas SET nome = ? WHERE id = ?", (novo_nome.upper(), disciplina_id))
        self.conn.commit()
    
    def excluir_disciplina(self, disciplina_id):
        """
        Exclui uma disciplina e TODAS as suas turmas com limpeza manual completa
        ⭐ CORREÇÃO: Limpeza dupla para garantir que não fiquem órfãos
        """
        cursor = self.conn.cursor()
        
        # Busca todas as turmas da disciplina
        cursor.execute("SELECT id FROM turmas WHERE disciplina_id = ?", (disciplina_id,))
        turmas = cursor.fetchall()
        
        # Limpa dados de cada turma MANUALMENTE (proteção extra)
        for turma in turmas:
            turma_id = turma[0]
            cursor.execute("DELETE FROM alunos WHERE turma_id = ?", (turma_id,))
            cursor.execute("DELETE FROM atividades WHERE turma_id = ?", (turma_id,))
            cursor.execute("DELETE FROM planejamento WHERE turma_id = ?", (turma_id,))
            cursor.execute("DELETE FROM presencas WHERE turma_id = ?", (turma_id,))
            cursor.execute("DELETE FROM turmas WHERE id = ?", (turma_id,))
        
        # Finalmente deleta a disciplina
        cursor.execute("DELETE FROM disciplinas WHERE id = ?", (disciplina_id,))
        self.conn.commit()
        
        print(f"✅ Disciplina {disciplina_id} e suas {len(turmas)} turmas removidas com sucesso!")
    
    # ==================== MÉTODOS DE TURMAS ====================
    
    def salvar_turma(self, nome, disciplina_id):
        """Salva uma nova turma vinculada a uma disciplina"""
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO turmas (nome, disciplina_id) VALUES (?, ?)", (nome.upper(), disciplina_id))
        self.conn.commit()
        return cursor.lastrowid
    
    def buscar_turmas_por_disciplina(self, disciplina_id):
        """Retorna todas as turmas de uma disciplina"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, nome FROM turmas WHERE disciplina_id = ? AND ativo = 1 ORDER BY nome", (disciplina_id,))
        return cursor.fetchall()
    
    def buscar_turma_id(self, nome_turma):
        """Busca o ID da turma pelo nome"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM turmas WHERE nome = ? AND ativo = 1", (nome_turma.upper(),))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    
    def buscar_turma_nome(self, turma_id):
        """Busca o nome da turma pelo ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT nome FROM turmas WHERE id = ?", (turma_id,))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    def excluir_turma(self, turma_id):
        """Exclui uma turma com limpeza manual completa em transação única"""
        cursor = self.conn.cursor()
        
        try:
            # 1. Ativa chaves estrangeiras
            self.conn.execute("PRAGMA foreign_keys = ON;")
            
            # 2. Busca os IDs dos alunos antes de qualquer deleção
            cursor.execute("SELECT id FROM alunos WHERE turma_id = ?", (turma_id,))
            # Ajuste aqui: se o seu row_factory retornar dicionário/Row, use row['id']. 
            # Se retornar tupla normal, use row[0]. Na dúvida, esta linha abaixo resolve ambos:
            ids_alunos = [row['id'] if isinstance(row, dict) or hasattr(row, 'keys') else row[0] 
                          for row in cursor.fetchall()]
            
            # 3. Se houver alunos, limpa o histórico deles primeiro
            if ids_alunos:
                placeholders = ",".join("?" for _ in ids_alunos)
                cursor.execute(f"DELETE FROM notas WHERE aluno_id IN ({placeholders})", ids_alunos)
                cursor.execute(f"DELETE FROM presencas WHERE aluno_id IN ({placeholders})", ids_alunos)
                cursor.execute(f"DELETE FROM ocorrencias WHERE aluno_id IN ({placeholders})", ids_alunos)
                # Agora apaga os alunos
                cursor.execute(f"DELETE FROM alunos WHERE turma_id = ?", (turma_id,))
            
            # 4. Limpa os dados periféricos da turma
            cursor.execute("DELETE FROM atividades WHERE turma_id = ?", (turma_id,))
            cursor.execute("DELETE FROM planejamento WHERE turma_id = ?", (turma_id,))
            cursor.execute("DELETE FROM presencas WHERE turma_id = ?", (turma_id,))
            
            # 5. Por fim, deleta a turma
            cursor.execute("DELETE FROM turmas WHERE id = ?", (turma_id,))
            
            # Só commitamos uma vez aqui no final!
            self.conn.commit()
            print(f"✅ Banco: Turma {turma_id} excluída com sucesso.")
            return True
            
        except Exception as e:
            print(f"❌ Erro no Banco ao excluir turma: {e}")
            self.conn.rollback()
            return False


    # ==================== MÉTODOS DE ALUNOS ====================
    
    def salvar_aluno(self, nome, turma_id, matricula=""):
        """Salva um novo aluno"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO alunos (nome, turma_id, matricula)
            VALUES (?, ?, ?)
        ''', (nome.upper(), turma_id, matricula))
        self.conn.commit()
        return cursor.lastrowid

    def buscar_aluno_por_nome(self, nome, turma_id):
        """Verifica se aluno já existe na turma"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM alunos WHERE nome = ? AND turma_id = ?",
            (nome, turma_id)
        )
        return cursor.fetchone() is not None

    def buscar_alunos_por_turma(self, turma_id):
        """Retorna todos os alunos de uma turma (como dicionários)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, nome FROM alunos WHERE turma_id = ? AND ativo = 1 ORDER BY nome", (turma_id,))
        return [{'id': row[0], 'nome': row[1]} for row in cursor.fetchall()]
    
    def buscar_aluno_por_id(self, aluno_id):
        """Retorna dados de um aluno específico"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, nome, turma_id, matricula FROM alunos WHERE id = ?", (aluno_id,))
        resultado = cursor.fetchone()
        if resultado:
            return {'id': resultado[0], 'nome': resultado[1], 'turma_id': resultado[2], 'matricula': resultado[3]}
        return None
    
    def excluir_aluno(self, aluno_id):
        """Exclui um aluno (CASCADE remove notas e ocorrências)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM alunos WHERE id = ?", (aluno_id,))
        self.conn.commit()
    
    # ==================== MÉTODOS DE ATIVIDADES ====================
    
    def salvar_atividade(self, nome, turma_id, valor=10.0, trimestre=1, tipo="normal"):
        """Salva uma nova atividade avaliativa"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO atividades (nome, turma_id, valor, trimestre, tipo)
            VALUES (?, ?, ?, ?, ?)
        ''', (nome, turma_id, valor, trimestre, tipo))
        self.conn.commit()
        return cursor.lastrowid
    
    def buscar_atividades_por_turma(self, turma_id):
        """Retorna todas as atividades de uma turma (como dicionários)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, nome, valor, trimestre, tipo
            FROM atividades
            WHERE turma_id = ?
            ORDER BY data_criacao DESC
        ''', (turma_id,))
        
        atividades = []
        for row in cursor.fetchall():
            atividades.append({
                'id': row[0],
                'nome': row[1],
                'valor': row[2],
                'trimestre': row[3],
                'tipo': row[4]
            })
        return atividades
    
    def buscar_atividade_por_id(self, atividade_id):
        """Retorna uma atividade específica"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, nome, turma_id, valor, trimestre, tipo
            FROM atividades WHERE id = ?
        ''', (atividade_id,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'nome': row[1],
                'turma_id': row[2],
                'valor': row[3],
                'trimestre': row[4],
                'tipo': row[5]
            }
        return None
    
    def excluir_atividade(self, atividade_id):
        """Exclui uma atividade (CASCADE remove as notas)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM atividades WHERE id = ?", (atividade_id,))
        self.conn.commit()
    
    # ==================== MÉTODOS DE NOTAS ====================
    
    def salvar_nota(self, aluno_id, atividade_id, nota):
        """Salva ou atualiza a nota de um aluno em uma atividade"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO notas (aluno_id, atividade_id, nota, data_lancamento)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (aluno_id, atividade_id, nota))
        self.conn.commit()
    
    def salvar_nota_final(self, aluno_id, atividade_id, nota):
        """Alias para salvar_nota (compatibilidade)"""
        self.salvar_nota(aluno_id, atividade_id, nota)
    
    def lancar_nota(self, aluno_id, atividade_id, nota):
        """Alias para salvar_nota (compatibilidade com scanner)"""
        self.salvar_nota(aluno_id, atividade_id, nota)
    
    def buscar_nota_aluno(self, aluno_id, atividade_id):
        """Retorna a nota de um aluno em uma atividade específica"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT nota FROM notas WHERE aluno_id = ? AND atividade_id = ?", (aluno_id, atividade_id))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    
    def buscar_notas_aluno_trimestre(self, aluno_id, trimestre, tipo="normal"):
        """Retorna todas as notas de um aluno em um trimestre"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT a.nome, n.nota, a.valor
            FROM notas n
            JOIN atividades a ON n.atividade_id = a.id
            WHERE n.aluno_id = ? AND a.trimestre = ? AND a.tipo = ?
            ORDER BY a.data_criacao
        ''', (aluno_id, trimestre, tipo))
        
        notas = []
        for row in cursor.fetchall():
            notas.append({
                'nome': row[0],
                'nota': row[1],
                'valor_maximo': row[2]
            })
        return notas
    
    def buscar_notas_individuais_trimestre(self, aluno_id, trimestre, tipo="normal"):
        """Retorna pares (nome_atividade, nota) para o relatório"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT a.nome, n.nota
            FROM notas n
            JOIN atividades a ON n.atividade_id = a.id
            WHERE n.aluno_id = ? AND a.trimestre = ? AND a.tipo = ?
            ORDER BY a.data_criacao
        ''', (aluno_id, trimestre, tipo))
        return cursor.fetchall()

    def buscar_notas_trimestre_turma(self, turma_id, trimestre):
        """Busca a nota final (ou média) de cada aluno da turma no trimestre."""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                SELECT a.nome, 
                       MAX(IFNULL(n.nota, 0)) as nota_final
                FROM alunos a
                LEFT JOIN notas n ON a.id = n.aluno_id
                LEFT JOIN atividades at ON n.atividade_id = at.id
                WHERE a.turma_id = ? AND (at.trimestre = ? OR at.trimestre IS NULL)
                GROUP BY a.id
                ORDER BY a.nome
            ''', (turma_id, trimestre))
            return cursor.fetchall()
        except Exception as e:
            print(f"Erro ao buscar notas da turma: {e}")
            return []

    def buscar_dados_trimestre(self, aluno_id, turma_id, trimestre):
        """Retorna dados consolidados do trimestre"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT SUM(n.nota), COUNT(n.nota)
            FROM notas n
            JOIN atividades a ON n.atividade_id = a.id
            WHERE n.aluno_id = ? AND a.trimestre = ? AND a.tipo = 'normal'
        ''', (aluno_id, trimestre))
        resultado_norm = cursor.fetchone()
        soma_normais = resultado_norm[0] if resultado_norm[0] else 0
        
        cursor.execute('''
            SELECT n.nota
            FROM notas n
            JOIN atividades a ON n.atividade_id = a.id
            WHERE n.aluno_id = ? AND a.trimestre = ? AND a.tipo = 'recuperacao'
            ORDER BY a.data_criacao DESC LIMIT 1
        ''', (aluno_id, trimestre))
        resultado_rec = cursor.fetchone()
        nota_recuperacao = resultado_rec[0] if resultado_rec else 0
        
        nota_final = max(soma_normais, nota_recuperacao) if nota_recuperacao > 0 else soma_normais
        return (soma_normais, nota_recuperacao, nota_final, 0)
    
    # ==================== MÉTODOS DE PRESENÇA (CHAMADA) ====================
    
    def salvar_presenca(self, aluno_id, turma_id, data, tema, status, justificativa="", trimestre=None):
        """Salva a presença de um aluno (VERSÃO ATUALIZADA COM TRIMESTRE)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO presencas (aluno_id, turma_id, data, tema, status, justificativa, trimestre)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (aluno_id, turma_id, data, tema, status, justificativa, trimestre))
        self.conn.commit()

    def salvar_planejamento_direto(self, data, tema, turma_id, trimestre, status=1):
        """Cria uma entrada no planejamento vinculada à nova chamada"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO planejamento (data_aula, titulo, turma_id, trimestre, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (data, tema.upper(), turma_id, trimestre, status))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Erro ao salvar planejamento direto: {e}")
            return False

    def verificar_presenca_existente(self, turma_id, data):
        """Verifica se já existe alguma chamada para esta turma nesta data"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM presencas WHERE turma_id = ? AND data = ?", (turma_id, data))
        return cursor.fetchone()[0] > 0
    
    def buscar_resumo_aula_salva(self, turma_id, data, tema):
        """Retorna contagem de faltas e presenças"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT status, COUNT(*) as total 
            FROM presencas 
            WHERE turma_id = ? AND data = ? AND tema = ?
            GROUP BY status
        ''', (turma_id, data, tema))
        
        resultados = cursor.fetchall()
        resumo = {'presencas': 0, 'faltas': 0}
        for row in resultados:
            if row['status'] == 1: 
                resumo['presencas'] = row['total']
            else: 
                resumo['faltas'] = row['total']
        return resumo

    def buscar_detalhes_presencas_dia(self, turma_id, data):
        """Retorna os temas das aulas já registradas no dia"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT tema FROM presencas WHERE turma_id = ? AND data = ?", (turma_id, data))
        return [linha[0] for linha in cursor.fetchall()]

    def excluir_presenca_data(self, turma_id, data):
        """Remove todos os registros de presença de uma turma numa data específica"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM presencas WHERE turma_id = ? AND data = ?", (turma_id, data))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Erro ao excluir presenca: {e}")
            return False

    def excluir_presenca_especifica(self, turma_id, data, tema):
        """Remove apenas a aula selecionada pelo professor na lixeira"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM presencas WHERE turma_id = ? AND data = ? AND tema = ?", 
                          (turma_id, data, tema))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Erro ao excluir aula específica: {e}")
            return False

    def buscar_presencas_por_aluno(self, aluno_id, turma_id):
        """Retorna todas as presenças de um aluno"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT data, tema, status, justificativa, trimestre
            FROM presencas
            WHERE aluno_id = ? AND turma_id = ?
            ORDER BY data DESC
        ''', (aluno_id, turma_id))
        
        presencas = []
        for row in cursor.fetchall():
            presencas.append({
                'data': row[0],
                'tema': row[1],
                'status': row[2],
                'justificativa': row[3],
                'trimestre': row[4]
            })
        return presencas
    
    def buscar_historico_presenca_aluno(self, aluno_id, turma_id):
        """Retorna histórico de presenças para relatório (5 campos com trimestre)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT data, tema, status, justificativa, trimestre
            FROM presencas
            WHERE aluno_id = ? AND turma_id = ?
            ORDER BY data
        ''', (aluno_id, turma_id))
        return cursor.fetchall()
    
    def buscar_frequencia_aluno(self, aluno_id, turma_id):
        """Retorna (presencas, total_aulas) para cálculo de frequência"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM presencas WHERE aluno_id = ? AND turma_id = ? AND status = 1', 
                      (aluno_id, turma_id))
        presencas = cursor.fetchone()[0] or 0
        cursor.execute('SELECT COUNT(DISTINCT data) FROM presencas WHERE turma_id = ?', (turma_id,))
        total_aulas = cursor.fetchone()[0] or 0
        return (presencas, total_aulas)

    # ==================== MÉTODOS DE OCORRÊNCIAS (DIÁRIO) ====================
    
    def salvar_ocorrencia(self, aluno_id, categoria, texto, trimestre=None):
        """Salva uma ocorrência respeitando as datas do calendário letivo."""
        cursor = self.conn.cursor()
        if trimestre is None:
            data_atual = datetime.now().strftime("%Y-%m-%d")
            cal = self.buscar_calendario()
            
            if cal and all(c is not None for c in cal):
                try:
                    if cal[0] <= data_atual <= cal[1]: trimestre = 1
                    elif cal[2] <= data_atual <= cal[3]: trimestre = 2
                    elif cal[4] <= data_atual <= cal[5]: trimestre = 3
                    else: trimestre = 1
                except:
                    trimestre = 1
            else:
                mes = datetime.now().month
                trimestre = 1 if mes <= 4 else 2 if mes <= 8 else 3
        
        try:
            cursor.execute('''
                INSERT INTO ocorrencias (aluno_id, categoria, texto, trimestre)
                VALUES (?, ?, ?, ?)
            ''', (aluno_id, categoria.upper(), texto, trimestre))
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"❌ Erro ao salvar ocorrência: {e}")
            return None

    def buscar_ocorrencias(self, aluno_id):
        """Busca todas as ocorrências de um aluno para exibir no diário."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT data_hora, texto, trimestre
            FROM ocorrencias
            WHERE aluno_id = ?
            ORDER BY data_hora DESC
        ''', (aluno_id,))
        return cursor.fetchall()
        
    # ==================== MÉTODOS DE PLANEJAMENTO ====================
    
    def salvar_planejamento(self, data, tema, turma_id, trimestre=1):
        """Salva uma nova aula no cronograma"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO planejamento (data_aula, titulo, turma_id, trimestre)
            VALUES (?, ?, ?, ?)
        ''', (data, tema.upper(), turma_id, trimestre))
        self.conn.commit()

    def buscar_planejamentos_por_turma(self, turma_id, trimestre=None):
        """Retorna os planos de aula de uma turma, filtrados ou não"""
        cursor = self.conn.cursor()
        if trimestre:
            cursor.execute('''
                SELECT id, data_aula, titulo, status FROM planejamento 
                WHERE turma_id = ? AND trimestre = ? 
                ORDER BY data_aula ASC
            ''', (turma_id, trimestre))
        else:
            cursor.execute('''
                SELECT id, data_aula, titulo, status FROM planejamento 
                WHERE turma_id = ? 
                ORDER BY data_aula ASC
            ''', (turma_id,))
        return [dict(row) for row in cursor.fetchall()]

    def buscar_planejamentos_por_intervalo(self, turma_id, data_inicio, data_fim):
        """Busca aulas entre datas (útil para relatórios mensais)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, data_aula, titulo FROM planejamento 
            WHERE turma_id = ? AND data_aula BETWEEN ? AND ?
            ORDER BY data_aula ASC
        ''', (turma_id, data_inicio, data_fim))
        return [dict(row) for row in cursor.fetchall()]

    def atualizar_status_plano(self, plano_id, novo_status):
        """Marca o plano como Concluído (1) ou Pendente (0)"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE planejamento SET status = ? WHERE id = ?", (novo_status, plano_id))
        self.conn.commit()

    def atualizar_tema_aula_existente(self, turma_id, data, tema_antigo, tema_novo):
        """
        Atualiza o tema de uma aula tanto na tabela de planejamento 
        quanto na tabela de presenças (para manter a integridade).
        """
        cursor = self.conn.cursor()
        try:
            # 1. Atualiza nas Presenças
            cursor.execute('''
                UPDATE presencas 
                SET tema = ? 
                WHERE turma_id = ? AND data = ? AND tema = ?
            ''', (tema_novo.upper(), turma_id, data, tema_antigo))
            
            # 2. Atualiza no Planejamento
            cursor.execute('''
                UPDATE planejamento 
                SET titulo = ? 
                WHERE turma_id = ? AND data_aula = ? AND titulo = ?
            ''', (tema_novo.upper(), turma_id, data, tema_antigo))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Erro ao atualizar título no banco: {e}")
            return False

    def excluir_aula_planejada(self, id_turma, data, titulo):
        """Remove uma aula do planejamento"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                DELETE FROM planejamento 
                WHERE turma_id = ? AND data_aula = ? AND titulo = ?
            ''', (id_turma, data, titulo.upper()))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Erro ao excluir planejamento: {e}")
            return False

    def editar_planejamento(self, plano_id, data_aula, titulo, conteudo="", objetivos="", metodologia=""):
        """Edita um plano existente"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE planejamento SET 
            data_aula=?, titulo=?, conteudo=?, objetivos=?, metodologia=?
            WHERE id = ?
        ''', (data_aula, titulo.upper(), conteudo, objetivos, metodologia, plano_id))
        self.conn.commit()

    def excluir_planejamento(self, plano_id):
        """Remove um plano de aula"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM planejamento WHERE id = ?", (plano_id,))
        self.conn.commit()

    # ==================== MÉTODOS DE GABARITOS ====================
    
    def salvar_gabarito(self, atividade_id, versao, respostas):
        """Salva um gabarito de uma versão específica"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO gabaritos (atividade_id, versao, respostas)
            VALUES (?, ?, ?)
        ''', (atividade_id, versao, respostas))
        self.conn.commit()
    
    def buscar_gabaritos_atividade(self, atividade_id):
        """Retorna todos os gabaritos de uma atividade"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT versao, respostas
            FROM gabaritos
            WHERE atividade_id = ?
        ''', (atividade_id,))
        
        gabaritos = {}
        for row in cursor.fetchall():
            gabaritos[row[0]] = row[1]
        return gabaritos

        # ==================== MÉTODOS DE LIMPEZA E SANEAMENTO ====================

    def limpar_todos_alunos_turma(self, turma_id):
        """
        Remove TODOS os alunos de uma turma específica.
        Inclui alunos normais e fantasmas (órfãos).
        Retorna o número de alunos removidos.
        """
        cursor = self.conn.cursor()
        try:
            # PASSO 1: Busca todos os alunos vinculados a esse ID de turma
            cursor.execute("SELECT id, nome FROM alunos WHERE turma_id = ?", (turma_id,))
            alunos = cursor.fetchall()
            
            if not alunos:
                return 0
            
            # PASSO 2: Remove TODOS os registros relacionados a cada aluno (Garantia manual)
            for aluno in alunos:
                aluno_id = aluno['id']  # Acessando via nome da coluna devido ao Row factory
                
                # Remove notas, presenças e ocorrências vinculadas ao estudante
                cursor.execute("DELETE FROM notas WHERE aluno_id = ?", (aluno_id,))
                cursor.execute("DELETE FROM presencas WHERE aluno_id = ?", (aluno_id,))
                cursor.execute("DELETE FROM ocorrencias WHERE aluno_id = ?", (aluno_id,))
            
            # PASSO 3: Remove os registros dos alunos
            cursor.execute("DELETE FROM alunos WHERE turma_id = ?", (turma_id,))
            total_removidos = cursor.rowcount
            
            self.conn.commit()
            print(f"✅ Limpeza Concluída - Turma {turma_id}: {total_removidos} alunos removidos do sistema.")
            return total_removidos

        except Exception as e:
            print(f"❌ Erro ao limpar alunos da turma {turma_id}: {e}")
            self.conn.rollback()
            return 0

    def limpar_alunos_orfaos(self, turma_id=None):
        """
        Remove APENAS alunos órfãos (fantasmas cuja turma original deixou de existir).
        Se turma_id for fornecido, foca apenas nos órfãos com aquela marcação.
        Retorna o número de alunos removidos.
        """
        cursor = self.conn.cursor()
        try:
            # 🛡️ Inversão estratégica de ordem: Primeiro localizamos os IDs órfãos para 
            # apagar suas notas e dados periféricos, evitando gerar chaves estrangeiras inválidas.
            if turma_id:
                cursor.execute("""
                    SELECT id FROM alunos 
                    WHERE turma_id = ? AND turma_id NOT IN (SELECT id FROM turmas)
                """, (turma_id,))
            else:
                cursor.execute("""
                    SELECT id FROM alunos 
                    WHERE turma_id NOT IN (SELECT id FROM turmas) AND turma_id IS NOT NULL
                """)
                
            ids_orfaos = [row['id'] for row in cursor.fetchall()]
            
            if not ids_orfaos:
                return 0
                
            # Transforma a lista de IDs em uma string formatada para a cláusula IN (ex: "1, 4, 7")
            placeholders = ",".join("?" for _ in ids_orfaos)
            
            # 1. Apaga as dependências desses órfãos específicos
            cursor.execute(f"DELETE FROM notas WHERE aluno_id IN ({placeholders})", ids_orfaos)
            cursor.execute(f"DELETE FROM presencas WHERE aluno_id IN ({placeholders})", ids_orfaos)
            cursor.execute(f"DELETE FROM ocorrencias WHERE aluno_id IN ({placeholders})", ids_orfaos)
            
            # 2. Agora sim, remove os alunos fantasmas com segurança
            cursor.execute(f"DELETE FROM alunos WHERE id IN ({placeholders})", ids_orfaos)
            alunos_removidos = cursor.rowcount
            
            self.conn.commit()
            print(f"🧹 Saneamento Concluído: {alunos_removidos} registros órfãos eliminados.")
            return alunos_removidos

        except Exception as e:
            print(f"❌ Erro ao limpar registros órfãos: {e}")
            self.conn.rollback()
            return 0

    def limpar_alunos_orfãos(self):
        """
        Remove alunos que estão órfãos (turma_id não existe mais)
        ⭐ Útil para corrigir bancos já corrompidos antes da correção
        """
        cursor = self.conn.cursor()
        
        # Encontra e remove alunos com turma_id que não existe
        cursor.execute('''
            DELETE FROM alunos 
            WHERE turma_id NOT IN (SELECT id FROM turmas)
            AND turma_id IS NOT NULL
        ''')
        
        alunos_removidos = cursor.rowcount
        
        # Remove presenças de alunos órfãos
        cursor.execute('''
            DELETE FROM presencas 
            WHERE aluno_id NOT IN (SELECT id FROM alunos)
        ''')
        
        # Remove notas de alunos órfãos
        cursor.execute('''
            DELETE FROM notas 
            WHERE aluno_id NOT IN (SELECT id FROM alunos)
        ''')
        
        # Remove ocorrências de alunos órfãos
        cursor.execute('''
            DELETE FROM ocorrencias 
            WHERE aluno_id NOT IN (SELECT id FROM alunos)
        ''')
        
        self.conn.commit()
        print(f"✅ Limpeza concluída: {alunos_removidos} alunos órfãos removidos")
        return alunos_removidos

    def verificar_integridade_fks(self):
        """Verifica se todas as chaves estrangeiras estão consistentes"""
        cursor = self.conn.cursor()
        
        # Verifica turmas sem disciplina
        cursor.execute('''
            SELECT COUNT(*) FROM turmas t
            WHERE t.disciplina_id NOT IN (SELECT id FROM disciplinas)
        ''')
        turmas_orfas = cursor.fetchone()[0]
        
        # Verifica alunos sem turma
        cursor.execute('''
            SELECT COUNT(*) FROM alunos a
            WHERE a.turma_id NOT IN (SELECT id FROM turmas)
            AND a.turma_id IS NOT NULL
        ''')
        alunos_orfãos = cursor.fetchone()[0]
        
        # Verifica atividades sem turma
        cursor.execute('''
            SELECT COUNT(*) FROM atividades at
            WHERE at.turma_id NOT IN (SELECT id FROM turmas)
        ''')
        atividades_orfãs = cursor.fetchone()[0]
        
        # Verifica planejamento sem turma
        cursor.execute('''
            SELECT COUNT(*) FROM planejamento p
            WHERE p.turma_id NOT IN (SELECT id FROM turmas)
        ''')
        planejamento_orfão = cursor.fetchone()[0]
        
        # Verifica presenças sem turma
        cursor.execute('''
            SELECT COUNT(*) FROM presencas pr
            WHERE pr.turma_id NOT IN (SELECT id FROM turmas)
        ''')
        presencas_orfãs = cursor.fetchone()[0]
        
        print(f"🔍 Diagnóstico de Integridade do Banco:")
        print(f"   🏫 Turmas órfãs: {turmas_orfas}")
        print(f"   👨‍🎓 Alunos órfãos: {alunos_orfãos}")
        print(f"   📝 Atividades órfãs: {atividades_orfãs}")
        print(f"   📅 Planejamento órfão: {planejamento_orfão}")
        print(f"   ✅ Presenças órfãs: {presencas_orfãs}")
        
        return {
            'turmas_orfas': turmas_orfas,
            'alunos_orfãos': alunos_orfãos,
            'atividades_orfãs': atividades_orfãs,
            'planejamento_orfão': planejamento_orfão,
            'presencas_orfãs': presencas_orfãs
        }

    def diagnosticar_consistencia(self, turma_id, data, tema):
        """Verifica se os dados estão sincronizados entre planejamento e presenças"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM planejamento 
            WHERE turma_id = ? AND data_aula = ? AND titulo = ?
        ''', (turma_id, data, tema))
        planejamento = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM presencas 
            WHERE turma_id = ? AND data = ? AND tema = ?
        ''', (turma_id, data, tema))
        presencas = cursor.fetchone()[0]
        
        print(f"🔍 Diagnóstico - Turma {turma_id}:")
        print(f"   Planejamento: {planejamento} registros")
        print(f"   Presenças: {presencas} registros")
        print(f"   Sincronizado: {planejamento == presencas}")
        
        return planejamento == presencas

    def excluir_aula_completa(self, turma_id, data, tema):
        """Remove uma aula do planejamento E das presenças"""
        cursor = self.conn.cursor()
        
        # 1. Exclui do planejamento
        cursor.execute("""
            DELETE FROM planejamento 
            WHERE turma_id = ? AND data_aula = ? AND titulo = ?
        """, (turma_id, data, tema))
        linhas_planejamento = cursor.rowcount
        
        # 2. Exclui das presenças
        cursor.execute("""
            DELETE FROM presencas 
            WHERE turma_id = ? AND data = ? AND tema = ?
        """, (turma_id, data, tema))
        linhas_presencas = cursor.rowcount
        
        self.conn.commit()
        
        total = linhas_planejamento + linhas_presencas
        print(f"✅ Removidas {total} referências da aula {data} - {tema} ({linhas_planejamento} plan / {linhas_presencas} pres)")
        
        return total > 0

    # ==================== MÉTODOS DE CONSULTA SINCRONIZADA ====================

    def obter_total_aulas_planejadas_trimestre(self, turma_id, trimestre):
        """
        Retorna o total de aulas PLANEJADAS no trimestre
        Fonte: tabela planejamento (o que o professor programou)
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM planejamento 
            WHERE turma_id = ? AND trimestre = ?
        ''', (turma_id, trimestre))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else 0

    def obter_frequencia_aluno_consolidada(self, aluno_id, turma_id, trimestre=None):
        """
        Retorna frequência do aluno comparando:
        - Total planejado (do planejamento)
        - Presenças reais (da tabela presencas)
        
        Retorna dicionário com:
        - total_planejado: total de aulas planejadas no período
        - presencas: quantas vezes o aluno esteve presente
        - faltas: quantas faltas o aluno teve
        - percentual: percentual de presença
        """
        cursor = self.conn.cursor()
        
        if trimestre:
            # Total planejado no trimestre
            cursor.execute('''
                SELECT COUNT(*) FROM planejamento 
                WHERE turma_id = ? AND trimestre = ?
            ''', (turma_id, trimestre))
            total_planejado = cursor.fetchone()[0] or 0
            
            # Presenças reais do aluno no trimestre
            cursor.execute('''
                SELECT COUNT(*) FROM presencas 
                WHERE aluno_id = ? AND turma_id = ? AND trimestre = ? AND status = 1
            ''', (aluno_id, turma_id, trimestre))
            presencas_reais = cursor.fetchone()[0] or 0
            
        else:
            # Ano todo
            cursor.execute('''
                SELECT COUNT(*) FROM planejamento 
                WHERE turma_id = ?
            ''', (turma_id,))
            total_planejado = cursor.fetchone()[0] or 0
            
            cursor.execute('''
                SELECT COUNT(*) FROM presencas 
                WHERE aluno_id = ? AND turma_id = ? AND status = 1
            ''', (aluno_id, turma_id))
            presencas_reais = cursor.fetchone()[0] or 0
        
        faltas = total_planejado - presencas_reais
        percentual = (presencas_reais / total_planejado * 100) if total_planejado > 0 else 100.0
        
        return {
            'total_planejado': total_planejado,
            'presencas': presencas_reais,
            'faltas': max(faltas, 0),
            'percentual': round(percentual, 1)
        }

    def obter_frequencia_detalhada_para_relatorio(self, aluno_id, turma_id, trimestre):
        """
        Retorna dados de frequência para o relatório:
        - Lista de aulas planejadas (com status de presença do aluno)
        
        Retorna lista de dicionários com:
        - data: data da aula
        - tema: tema/título da aula
        - status: 1=presente, 0=falta, None=não registrado
        - justificativa: justificativa da falta (se houver)
        """
        cursor = self.conn.cursor()
        
        # Busca todas as aulas planejadas para o trimestre
        cursor.execute('''
            SELECT p.data_aula, p.titulo, p.trimestre
            FROM planejamento p
            WHERE p.turma_id = ? AND p.trimestre = ?
            ORDER BY p.data_aula ASC
        ''', (turma_id, trimestre))
        
        aulas_planejadas = cursor.fetchall()
        
        # Para cada aula, busca se o aluno tem registro de presença
        resultado = []
        for aula in aulas_planejadas:
            data_aula, titulo, tri = aula
            
            # Verifica se o aluno tem registro de presença nesta aula
            cursor.execute('''
                SELECT status, justificativa 
                FROM presencas 
                WHERE aluno_id = ? AND turma_id = ? AND data = ? AND tema = ?
            ''', (aluno_id, turma_id, data_aula, titulo))
            
            presenca = cursor.fetchone()
            
            if presenca:
                status = presenca[0]  # 1=presente, 0=falta
                justificativa = presenca[1] or ""
            else:
                status = None
                justificativa = ""
            
            resultado.append({
                'data': data_aula,
                'tema': titulo,
                'status': status,
                'justificativa': justificativa,
                'trimestre': tri
            })
        
        return resultado

    # ==================== MÉTODOS DE ESTATÍSTICAS E RELATÓRIOS ====================
    
    def calcular_media_turma_atividade(self, atividade_id):
        """Calcula a média da turma em uma atividade"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT AVG(nota) FROM notas WHERE atividade_id = ?', (atividade_id,))
        resultado = cursor.fetchone()
        return resultado[0] if resultado[0] else 0
    
    def calcular_aproveitamento_turma(self, turma_id, trimestre=None):
        """Calcula o aproveitamento geral da turma"""
        cursor = self.conn.cursor()
        if trimestre:
            query = '''
                SELECT AVG(n.nota) FROM notas n
                JOIN atividades a ON n.atividade_id = a.id
                WHERE a.turma_id = ? AND a.trimestre = ?
            '''
            cursor.execute(query, (turma_id, trimestre))
        else:
            query = '''
                SELECT AVG(n.nota) FROM notas n
                JOIN atividades a ON n.atividade_id = a.id
                WHERE a.turma_id = ?
            '''
            cursor.execute(query, (turma_id,))
        resultado = cursor.fetchone()
        return resultado[0] if resultado[0] else 0
    
    def gerar_relatorio_aluno(self, aluno_id, turma_id):
        """Gera um relatório completo do aluno"""
        aluno = self.buscar_aluno_por_id(aluno_id)
        if not aluno:
            return None
        
        relatorio = {
            'aluno': aluno,
            'frequencia': self.buscar_frequencia_aluno(aluno_id, turma_id),
            'notas_trimestre_1': self.buscar_notas_aluno_trimestre(aluno_id, 1),
            'notas_trimestre_2': self.buscar_notas_aluno_trimestre(aluno_id, 2),
            'notas_trimestre_3': self.buscar_notas_aluno_trimestre(aluno_id, 3),
            'ocorrencias': self.buscar_ocorrencias(aluno_id),
            'presencas': self.buscar_presencas_por_aluno(aluno_id, turma_id)
        }
        for i in range(1, 4):
            soma, rec, final, _ = self.buscar_dados_trimestre(aluno_id, turma_id, i)
            relatorio[f'nota_final_{i}'] = final
        return relatorio
    
    # ==================== MÉTODOS DE UTILITÁRIOS ====================
    
    def fazer_backup(self, caminho_backup=None):
        """Faz backup do banco de dados"""
        if caminho_backup is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if platform == 'android':
                from android.storage import primary_external_storage_path
                base = primary_external_storage_path()
                caminho_backup = os.path.join(base, "Documents", "Gabaritus", f"backup_{timestamp}.db")
                os.makedirs(os.path.dirname(caminho_backup), exist_ok=True)
            else:
                caminho_backup = f"backup_gabaritus_{timestamp}.db"
        
        import shutil
        shutil.copy2(self.db_path, caminho_backup)
        
        cursor = self.conn.cursor()
        cursor.execute("UPDATE config SET ultimo_backup = ?", (datetime.now().isoformat(),))
        self.conn.commit()
        return caminho_backup
    
    def restaurar_backup(self, caminho_backup):
        """Restaura um backup do banco de dados"""
        if os.path.exists(caminho_backup):
            self.conn.close()
            import shutil
            shutil.copy2(caminho_backup, self.db_path)
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            # Reativa chaves estrangeiras após restauração
            self.conn.execute("PRAGMA foreign_keys = ON")
            return True
        return False
    
    def limpar_dados_teste(self):
        """Remove todos os dados (útil para testes)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM notas")
        cursor.execute("DELETE FROM presencas")
        cursor.execute("DELETE FROM ocorrencias")
        cursor.execute("DELETE FROM atividades")
        cursor.execute("DELETE FROM alunos")
        cursor.execute("DELETE FROM turmas")
        cursor.execute("DELETE FROM disciplinas")
        cursor.execute("DELETE FROM gabaritos")
        self.conn.commit()
    
    # ==================== AUXILIARES DE CALENDÁRIO/RELATÓRIOS ====================
    
    def obter_limites_trimestre(self, trimestre):
        """Retorna (inicio, fim) baseada no calendário salvo"""
        cal = self.buscar_calendario()
        if not cal: 
            return (None, None)
        mapa = {1: (0, 1), 2: (2, 3), 3: (4, 5)}
        idx_ini, idx_fim = mapa.get(trimestre, (0, 1))
        return cal[idx_ini], cal[idx_fim]

    def buscar_frequencia_detalhada_tri(self, aluno_id, turma_id, trimestre):
        """Retorna (faltas, total, lista_aulas) usando o campo trimestre ou calendário"""
        cursor = self.conn.cursor()
        
        # Tenta usar o campo trimestre primeiro (mais rápido e preciso)
        cursor.execute('''
            SELECT data, tema, status, trimestre FROM presencas 
            WHERE aluno_id = ? AND turma_id = ? AND trimestre = ?
            ORDER BY data ASC
        ''', (aluno_id, turma_id, trimestre))
        
        resultados = cursor.fetchall()
        
        # Se não encontrou com trimestre, usa o calendário como fallback
        if not resultados:
            ini, fim = self.obter_limites_trimestre(trimestre)
            if ini and fim:
                cursor.execute('''
                    SELECT data, tema, status FROM presencas 
                    WHERE aluno_id = ? AND turma_id = ? AND data BETWEEN ? AND ?
                    ORDER BY data ASC
                ''', (aluno_id, turma_id, ini, fim))
                resultados = cursor.fetchall()
        
        total = len(resultados)
        faltas = sum(1 for r in resultados if r[2] == 0)
        return faltas, total, resultados
 
    def buscar_carga_planejada_trimestre(self, turma_id, trimestre):
        """Busca o total de aulas planejadas"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM planejamento WHERE turma_id = ? AND trimestre = ?", 
                      (turma_id, trimestre))
        res = cursor.fetchone()
        return res[0] if res else 0

    def buscar_carga_planejada_anual(self, turma_id, tri_limite):
        """Soma a carga de todos os trimestres até o atual para o acumulado"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM planejamento WHERE turma_id = ? AND trimestre <= ?", 
                      (turma_id, tri_limite))
        res = cursor.fetchone()
        return res[0] if res else 0

    def buscar_aulas_por_trimestre(self, turma_id, trimestre):
        """Busca os temas de aula registrados no planejamento para um trimestre específico."""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                SELECT data_aula as data, titulo as tema 
                FROM planejamento 
                WHERE turma_id = ? AND trimestre = ?
                ORDER BY data_aula ASC
            ''', (turma_id, trimestre))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Erro ao buscar aulas por trimestre: {e}")
            return []

    def buscar_faltas_aluno(self, aluno_id, turma_id, trimestre=None):
        """Busca apenas as exceções (status = 0)"""
        cursor = self.conn.cursor()
        if trimestre:
            cursor.execute('''
                SELECT COUNT(*) FROM presencas 
                WHERE aluno_id = ? AND turma_id = ? AND status = 0 AND trimestre = ?
            ''', (aluno_id, turma_id, trimestre))
        else:
            cursor.execute('''
                SELECT COUNT(*) FROM presencas 
                WHERE aluno_id = ? AND turma_id = ? AND status = 0
            ''', (aluno_id, turma_id))
        res = cursor.fetchone()
        return res[0] if res else 0

    def buscar_nomes_faltosos_aula(self, turma_id, data, tema):
        """Retorna lista de strings com nomes dos alunos faltosos"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT a.nome 
            FROM presencas p
            JOIN alunos a ON p.aluno_id = a.id
            WHERE p.turma_id = ? AND p.data = ? AND p.tema = ? AND p.status = 0
            ORDER BY a.nome
        ''', (turma_id, data, tema))
        return [linha[0] for linha in cursor.fetchall()]

    def calcular_frequencia_acumulada_anual(self, aluno_id, turma_id, tri_limite):
        """Retorna (faltas_acumuladas, total_aulas_planejadas) usando trimestre"""
        cursor = self.conn.cursor()
        try:
            # Soma faltas até o trimestre limite
            cursor.execute('''
                SELECT COUNT(*) FROM presencas 
                WHERE aluno_id = ? AND turma_id = ? AND status = 0 AND trimestre <= ?
            ''', (aluno_id, turma_id, tri_limite))
            total_faltas = cursor.fetchone()[0] or 0

            # Soma aulas planejadas até o trimestre limite
            cursor.execute('''
                SELECT COUNT(*) FROM planejamento 
                WHERE turma_id = ? AND trimestre <= ?
            ''', (turma_id, tri_limite))
            total_aulas_planejadas = cursor.fetchone()[0] or 0
            
            return total_faltas, total_aulas_planejadas
        except Exception as e:
            print(f"Erro ao calcular frequência acumulada: {e}")
            return 0, 0

    def buscar_dados_separados_trimestre(self, aluno_id, trimestre):
        """Retorna (notas_normais, notas_recuperacao) separadamente"""
        normais = [{'nome': r[0], 'nota': r[1]} for r in self.buscar_notas_individuais_trimestre(aluno_id, trimestre, 'normal')]
        recups = [{'nome': r[0], 'nota': r[1]} for r in self.buscar_notas_individuais_trimestre(aluno_id, trimestre, 'recuperacao')]
        return normais, recups

    def calcular_acumulado_ate_tri(self, aluno_id, turma_id, trimestre_alvo):
        """Soma as notas finais calculadas em escadinha até o trimestre selecionado"""
        soma_acumulada = 0.0
        for t in range(1, trimestre_alvo + 1):
            dados = self.buscar_dados_trimestre(aluno_id, turma_id, t)
            if dados and len(dados) > 2:
                soma_acumulada += (dados[2] if dados[2] is not None else 0.0)
        return soma_acumulada

    def fechar(self):
        """Fecha a conexão com o banco de dados"""
        if self.conn:
            self.conn.close()
    
    def __del__(self):
        """Destrutor para fechar a conexão de forma segura"""
        try:
            self.fechar()
        except:
            pass


# Script de diagnóstico e correção para bancos existentes
if __name__ == "__main__":
    print("=" * 60)
    print("🔧 GABARITUS - FERRAMENTA DE DIAGNÓSTICO E CORREÇÃO")
    print("=" * 60)
    
    db = Database("gabaritus_v3.db")
    
    print("\n📊 DIAGNÓSTICO INICIAL:")
    print("-" * 40)
    integridade = db.verificar_integridade_fks()
    
    if any(integridade.values()):
        print("\n⚠️ INCONSISTÊNCIAS ENCONTRADAS!")
        resposta = input("\nDeseja corrigir automaticamente? (S/N): ").upper()
        
        if resposta == 'S':
            print("\n🔧 INICIANDO CORREÇÃO...")
            alunos_removidos = db.limpar_alunos_orfãos()
            print(f"✅ Correção concluída! {alunos_removidos} registros inconsistentes removidos.")
            
            print("\n📊 DIAGNÓSTICO FINAL:")
            db.verificar_integridade_fks()
        else:
            print("\n❌ Correção cancelada pelo usuário.")
    else:
        print("\n✅ BANCO DE DADOS CONSISTENTE! Nenhuma correção necessária.")
    
    print("\n" + "=" * 60)
    print(f"📁 Caminho do banco: {db.db_path}")
    print("=" * 60)
    
    db.fechar()