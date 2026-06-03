import os
import sys
import random
import csv
import json
import numpy as np
from datetime import datetime

# Importações de processamento de imagem e relatórios
import cv2
import imutils
import pyzbar
from fpdf import FPDF

# Kivy Base e Utilitários
from kivy.utils import platform
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

# Kivy Propriedades
from kivy.properties import (
    BooleanProperty, StringProperty, ObjectProperty, 
    ListProperty, DictProperty, NumericProperty
)

# KivyMD Base
from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.filemanager import MDFileManager

# KivyMD Componentes Interativos
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.pickers import MDDatePicker
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.expansionpanel import MDExpansionPanel, MDExpansionPanelOneLine
from kivymd.uix.menu import MDDropdownMenu

# KivyMD Listas e Seleções
from kivymd.uix.list import (
    MDList, OneLineListItem, TwoLineListItem,
    TwoLineAvatarIconListItem, IconRightWidget, IconLeftWidget,
    OneLineAvatarIconListItem, OneLineIconListItem, ILeftBodyTouch
)

# Configurações específicas para Android
if platform == 'android':
    from android.permissions import request_permissions, Permission

# Módulos locais do seu projeto
from gabaritus import Database
from gerenciador_planilha import GerenciadorPlanilha
from gerenciador_relatorio import GeradorRelatorio

# 1. Classes auxiliares para o diálogo de seleção
# --- CLASSES ATUALIZADAS PARA EVITAR O RECURSION ERROR ---
from kivymd.uix.list import OneLineIconListItem, ILeftBodyTouch

class LeftCheckbox(MDCheckbox, ILeftBodyTouch):
    '''Checkbox à esquerda padrão'''
    pass

class ItemSelecao(OneLineIconListItem): # Mudamos para OneLineIconListItem
    def __init__(self, text, **kwargs):
        super().__init__(text=text, **kwargs)
        # Em vez de forçar IDs, criamos o ícone/checkbox da forma oficial
        self.checkbox = LeftCheckbox()
        self.add_widget(self.checkbox)

class ItemCheckDiario(MDBoxLayout):
    text = StringProperty()
    # Mantive sua lógica original de atualização
    def atualizar_selecao(self, texto, ativa):
        app = MDApp.get_running_app()
        try:
            tela = app.root.get_screen('diario_screen')
            if ativa:
                if texto not in tela.itens_selecionados:
                    tela.itens_selecionados.append(texto)
            else:
                if texto in tela.itens_selecionados:
                    tela.itens_selecionados.remove(texto)
        except:
            pass

class ListaPlanilhas(ScrollView):
    def __init__(self, itens, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = "250dp"
        self.lista = MDList() # Guardamos a referência da lista
        for item in itens:
            self.lista.add_widget(item)
        self.add_widget(self.lista)

class ConteudoCategoria(MDBoxLayout):

    pass

class ConteudoSelecaoAlunoDiario(MDBoxLayout):
    pass

class ConteudoDialogoChamada(MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Inicializamos a data, mas não mexemos nos IDs aqui ainda
        self.data_db = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def abrir_calendario(self):
        d = MDDatePicker()
        d.bind(on_save=self.definir_data)
        d.open()

    def definir_data(self, instance, value, date_range):
        # Proteção para evitar crash caso o ID não exista no KV
        if 'data_selecionada' in self.ids:
            hora_atual = datetime.now().strftime("%H:%M:%S")
            self.data_db = f"{value.strftime('%Y-%m-%d')} {hora_atual}"
            self.ids.data_selecionada.text = f"Data: {value.strftime('%d/%m/%Y')}"

# TELA GABARITO MESTRE
class ConteudoGabaritoMestre(MDBoxLayout):
    gabaritos = DictProperty({})

    def validar_texto(self, instance):
        instance.text = instance.text.upper().replace(" ", "")

    def gerar_e_exibir(self):
        mestre = self.ids.campo_mestre.text.upper().strip()
        try:
            qtd = int(self.ids.qtd_questoes.text)
        except:
            toast("Qtd inválida")
            return

        if len(mestre)!= qtd:
            toast(f"Esperado {qtd} letras")
            return

        res_base = list(mestre)
        final_text = ""
        temp_gabs = {}

        for letra in ['A', 'B', 'C', 'D']:
            temp_res = res_base[:]
            if letra!= 'A':
                random.shuffle(temp_res)
            str_res = "".join(temp_res)
            temp_gabs[letra] = str_res
            final_text += f"VERSÃO {letra}: {str_res}\n"

        self.gabaritos = temp_gabs
        self.ids.area_conferencia.text = final_text
        self.ids.btn_gerar_pdf.disabled = False
        MDApp.get_running_app().gabaritos_versoes = temp_gabs

    def acao_gerar_pdf(self, turma_final=None):
        app = MDApp.get_running_app()
        turma_alvo = turma_final if turma_final else app.turma_ativa

        if not turma_alvo or turma_alvo == "Turma":
            toast("Selecione uma turma primeiro!")
            return

        prof = app.db_manager.buscar_professor()
        turma_id = app.db_manager.buscar_turma_id(turma_alvo)
        alunos = app.db_manager.buscar_alunos_por_turma(turma_id)

        if not alunos:
            toast(f"Sem alunos na turma {turma_alvo}!")
            return

        atv_id = app.atividade_ativa_id if app.atividade_ativa_id else random.randint(100,999)
        nome_atv = app.atividade_ativa_nome if app.atividade_ativa_nome else "Atividade"

        try:
            # SALVAR JSON NA PASTA DA ATIVIDADE
            from gerador_pdf import normalizar
            caminho_base = "/storage/emulated/0/Documents/AppProfessor_Turmas" if platform == 'android' else os.path.join(os.path.expanduser("~"), "Documents", "AppProfessor_Turmas")
            nome_pasta = f"ATV_{atv_id}_{normalizar(nome_atv)}"
            pasta_atividade = os.path.join(caminho_base, normalizar(turma_alvo), nome_pasta)
            os.makedirs(pasta_atividade, exist_ok=True)

            caminho_json = os.path.join(pasta_atividade, f"gabarito_ID_{atv_id}.json")
            with open(caminho_json, 'w', encoding='utf-8') as f:
                json.dump(self.gabaritos, f, ensure_ascii=False, indent=4)

            caminho = gerador_pdf.gerar_folha_com_qrcode(
                turma=turma_alvo,
                escola=prof[3] if prof else "Escola Municipal",
                disciplina=prof[1] if prof else "Matéria",
                professor=prof[0] if prof else "Professor",
                atividade_nome=nome_atv,
                atividade_id=atv_id,
                lista_alunos=alunos,
                gabaritos_versoes=self.gabaritos
            )
            toast(f"PDF e Gabarito salvos na pasta {nome_pasta}!")
        except Exception as e:
            print(f"Erro PDF: {e}")
            toast(f"Erro: {str(e)}")

# --- TELAS DO SISTEMA ---
class TelaLogin(MDScreen):  # Alterado para MDScreen para seguir o padrão
    def on_pre_enter(self):
        try:
            self.ids.senha_login.text = ""
        except:
            pass

    def fazer_login(self):
        senha = self.ids.senha_login.text
        app = MDApp.get_running_app()
        
        # 1. Busca a senha cadastrada no banco
        senha_db = app.db_manager.buscar_senha()
        
        # 2. Verifica se a senha digitada está correta
        if senha == senha_db:
            # 3. Checa se o perfil do professor já foi preenchido
            prof = app.db_manager.buscar_professor()
            
            if prof:
                # Se o professor existe, vai para a seleção de DISCIPLINAS
                # Isso garante que app.disciplina_ativa_id seja preenchido depois
                self.manager.current = "disciplinas_screen"
            else:
                # Se não tem perfil (primeiro acesso), vai para o cadastro
                self.manager.current = "cadastro_prof_screen"
        else:
            from kivymd.toast import toast
            toast("Senha incorreta!")

    def recuperar_senha(self):
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton

        lay = MDBoxLayout(orientation="vertical", spacing="10dp", size_hint_y=None, height="100dp")
        self.senha_nova = MDTextField(hint_text="Digite a nova senha", password=True, mode="rectangle")
        lay.add_widget(self.senha_nova)
        
        self.d_senha = MDDialog(
            title="Redefinir Senha",
            type="custom",
            content_cls=lay,
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.d_senha.dismiss()),
                MDRaisedButton(
                    text="SALVAR", 
                    md_bg_color=(0.33, 0.42, 0.18, 1), 
                    on_release=self.salvar_nova_senha
                )
            ]
        )
        self.d_senha.open()

    def salvar_nova_senha(self, *a):
        from kivymd.toast import toast
        if not self.senha_nova.text:
            toast("Digite a nova senha")
            return
            
        app = MDApp.get_running_app()
        app.db_manager.atualizar_senha(self.senha_nova.text)
        self.d_senha.dismiss()
        toast("Senha alterada com sucesso!")


# TELA DE CADASTRO

class TelaCadastro(Screen):
    def salvar_perfil(self):
        app = MDApp.get_running_app()
        ids = self.ids

        if all([ids.nome_prof.text, ids.inst_prof.text]):
            app.db_manager.salvar_professor(
                ids.nome_prof.text,
                ids.esfera_prof.text,
                ids.inst_prof.text,
                ids.sec_prof.text
            )
            self.manager.current = "login_screen"
        else:
            toast("Campos obrigatórios vazios")

# TELA DISCIPLINA
from kivymd.uix.screen import MDScreen
from kivymd.app import MDApp
from kivymd.uix.list import (
    MDList, 
    OneLineListItem, 
    OneLineAvatarIconListItem, 
    IconLeftWidget, 
    IconRightWidget
)


from kivymd.uix.screen import MDScreen
from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDRectangleFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineAvatarIconListItem, OneLineListItem, IconLeftWidget, IconRightWidget, MDList
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.toast import toast
from kivy.metrics import dp

class TelaDisciplinas(MDScreen):
    def on_pre_enter(self):
        """Sempre atualiza a lista ao entrar na tela"""
        self.atualizar()

    def atualizar(self):
        """Limpa e preenche a lista de matérias com suporte a engrenagem"""
        self.ids.container_disciplinas.clear_widgets()
        app = MDApp.get_running_app()
        
        try:
            # Busca as matérias do banco de dados
            disciplinas = app.db_manager.buscar_disciplinas()
            
            if not disciplinas:
                self.ids.container_disciplinas.add_widget(
                    MDLabel(text="Nenhuma disciplina cadastrada.", halign="center", padding=(0, dp(20)))
                )
                return

            for disc in disciplinas:
                id_disc, nome_disc = disc[0], disc[1]

                # Criamos o item que permite ícones na esquerda e direita
                item = OneLineAvatarIconListItem(
                    text=str(nome_disc).upper(),
                    on_release=lambda x, i=id_disc, n=nome_disc: self.selecionar(i, n)
                )
                
                # Ícone da esquerda (Estilo livro)
                item.add_widget(IconLeftWidget(icon="book-open-variant"))
                
                # Ícone da direita (Engrenagem para gerenciar a disciplina específica)
                btn_opcoes = IconRightWidget(icon="cog-outline")
                btn_opcoes.bind(on_release=lambda x, i=id_disc, n=nome_disc: self.abrir_opcoes_disciplina(i, n))
                
                item.add_widget(btn_opcoes)
                self.ids.container_disciplinas.add_widget(item)
                
        except Exception as e:
            print(f"Erro ao carregar disciplinas: {e}")

    # ==================== GERENCIAMENTO DE TRIMESTRES (CALENDÁRIO) ====================

    def abrir_configuracao_trimestres(self):
        """Abre o popup para gerenciar as datas dos trimestres via engrenagem do TopBar"""
        app = MDApp.get_running_app()
        datas_existentes = app.db_manager.buscar_calendario()
        
        # Converte Row do SQLite para lista ou cria lista vazia
        self.datas_calendario = list(datas_existentes) if datas_existentes else [""] * 6
        
        conteudo = MDBoxLayout(orientation="vertical", spacing="12dp", size_hint_y=None, height=dp(250))
        
        def criar_linha_tri(label_text, idx_inicio, idx_fim):
            linha = MDBoxLayout(adaptive_height=True, spacing="10dp")
            linha.add_widget(MDLabel(text=label_text, bold=True, size_hint_x=0.3))
            
            # Botão Início
            btn_i = MDRectangleFlatButton(
                text=self.datas_calendario[idx_inicio] or "Início",
                size_hint_x=0.35,
                on_release=lambda x: self.abrir_calendario_seletor(idx_inicio, x)
            )
            # Botão Fim
            btn_f = MDRectangleFlatButton(
                text=self.datas_calendario[idx_fim] or "Fim",
                size_hint_x=0.35,
                on_release=lambda x: self.abrir_calendario_seletor(idx_fim, x)
            )
            linha.add_widget(btn_i)
            linha.add_widget(btn_f)
            return linha

        conteudo.add_widget(criar_linha_tri("1º Tri:", 0, 1))
        conteudo.add_widget(criar_linha_tri("2º Tri:", 2, 3))
        conteudo.add_widget(criar_linha_tri("3º Tri:", 4, 5))

        self.dialog_cal = MDDialog(
            title="Calendário Escolar",
            type="custom",
            content_cls=conteudo,
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialog_cal.dismiss()),
                MDRaisedButton(
                    text="SALVAR", 
                    md_bg_color=(0.33, 0.42, 0.18, 1),
                    on_release=lambda x: self.salvar_dados_calendario()
                ),
            ],
        )
        self.dialog_cal.open()

    def abrir_calendario_seletor(self, indice, botao_clicado):
        """Abre o seletor de data oficial"""
        from kivymd.uix.pickers import MDDatePicker
        
        picker = MDDatePicker()
        def on_save(instance, value, date_range):
            data_str = value.strftime("%Y-%m-%d")
            self.datas_calendario[indice] = data_str
            botao_clicado.text = data_str
            
        picker.bind(on_save=on_save)
        picker.open()

    def salvar_dados_calendario(self):
        app = MDApp.get_running_app()
        app.db_manager.salvar_calendario(self.datas_calendario)
        self.dialog_cal.dismiss()
        toast("Calendário escolar atualizado!")

    # ==================== OPÇÕES DA DISCIPLINA SELECIONADA ====================

    def abrir_opcoes_disciplina(self, id_d, nome):
        """Abre o menu para editar ou excluir uma disciplina específica"""
        conteudo = MDList()
        
        item_edit = OneLineListItem(text="📝 Editar Nome")
        item_edit.bind(on_release=lambda x: [self.menu_disc.dismiss(), self.preparar_edicao(id_d, nome)])
        
        item_del = OneLineListItem(text="🗑️ Excluir Disciplina", text_color=(0.8, 0, 0, 1))
        item_del.bind(on_release=lambda x: [self.menu_disc.dismiss(), self.confirmar_exclusao(id_d, nome)])
        
        conteudo.add_widget(item_edit)
        conteudo.add_widget(item_del)

        self.menu_disc = MDDialog(
            title=f"Gerenciar: {nome}",
            type="custom",
            content_cls=conteudo,
            buttons=[MDFlatButton(text="FECHAR", on_release=lambda x: self.menu_disc.dismiss())]
        )
        self.menu_disc.open()

    def confirmar_exclusao(self, id_d, nome):
        self.diag_conf = MDDialog(
            title="⚠️ ATENÇÃO!",
            text=f"Excluir '{nome}' apagará permanentemente tudo vinculado a ela. Continuar?",
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.diag_conf.dismiss()),
                MDRaisedButton(
                    text="EXCLUIR", 
                    md_bg_color=(0.8, 0, 0, 1), 
                    on_release=lambda x: self.executar_exclusao(id_d)
                )
            ]
        )
        self.diag_conf.open()

    def executar_exclusao(self, id_d):
        app = MDApp.get_running_app()
        app.db_manager.excluir_disciplina(id_d)
        self.diag_conf.dismiss()
        self.atualizar()
        toast("Removida com sucesso!")

    def preparar_edicao(self, id_d, nome_atual):
        self.campo_edicao = MDTextField(text=nome_atual, mode="rectangle", size_hint_y=None, height=dp(50))
        self.diag_edit = MDDialog(
            title="Renomear Disciplina",
            type="custom",
            content_cls=self.campo_edicao,
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.diag_edit.dismiss()),
                MDRaisedButton(
                    text="SALVAR", 
                    md_bg_color=(0.33, 0.42, 0.18, 1), 
                    on_release=lambda x: self.salvar_edicao(id_d)
                )
            ]
        )
        self.diag_edit.open()

    def salvar_edicao(self, id_d):
        novo_nome = self.campo_edicao.text.strip().upper()
        if novo_nome:
            app = MDApp.get_running_app()
            app.db_manager.editar_disciplina(id_d, novo_nome)
            self.diag_edit.dismiss()
            self.atualizar()
            toast("Atualizado!")

    def selecionar(self, id_disc, nome_disc):
        app = MDApp.get_running_app()
        app.disciplina_ativa_id = id_disc
        app.disciplina_ativa_nome = nome_disc
        self.manager.current = "turmas_screen"

    def mostrar_input_disciplina(self):
        self.campo_novo = MDTextField(hint_text="Ex: PORTUGUÊS", mode="rectangle")
        self.diag_novo = MDDialog(
            title="Nova Disciplina",
            type="custom",
            content_cls=self.campo_novo,
            buttons=[
                MDRaisedButton(
                    text="SALVAR", 
                    md_bg_color=(0.33, 0.42, 0.18, 1), 
                    on_release=lambda x: self.salvar_nova()
                )
            ]
        )
        self.diag_novo.open()

    def salvar_nova(self):
        if self.campo_novo.text:
            app = MDApp.get_running_app()
            app.db_manager.salvar_disciplina(self.campo_novo.text.upper())
            self.diag_novo.dismiss()
            self.atualizar()

    def fazer_logout(self):
        self.manager.current = "login_screen"

# TELA TURMA
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import TwoLineAvatarIconListItem, IconLeftWidget, IconRightWidget
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivymd.toast import toast
from kivymd.app import MDApp
from kivy.clock import Clock
from threading import Thread

class TelaTurmas(MDScreen):
    def on_pre_enter(self):
        """Atualiza o título e a lista ao entrar na tela"""
        app = MDApp.get_running_app()
        if 'label_materia' in self.ids:
            nome_m = getattr(app, 'disciplina_ativa_nome', 'Matéria')
            self.ids.label_materia.text = f"Matéria: {nome_m}"
        self.atualizar()

    def atualizar(self):
        """Lista as turmas vinculadas à disciplina ativa"""
        self.ids.container_turmas.clear_widgets()
        app = MDApp.get_running_app()

        try:
            id_d = getattr(app, 'disciplina_ativa_id', None)
            turmas = app.db_manager.buscar_turmas_por_disciplina(id_d)

            if not turmas:
                msg_label = MDLabel(
                    text="Nenhuma turma cadastrada\nClique no botão + para adicionar",
                    halign="center",
                    theme_text_color="Secondary",
                    size_hint_y=None,
                    height=100
                )
                self.ids.container_turmas.add_widget(msg_label)
                return

            for t in turmas:
                id_t, nome_t = t[0], t[1] 

                item = TwoLineAvatarIconListItem(
                    text=nome_t,
                    secondary_text="Toque para abrir a chamada",
                )
                item.bind(on_release=lambda x, n=nome_t, i=id_t: self.entrar(n, i))
                item.add_widget(IconLeftWidget(icon="account-group"))
                
                # Botão excluir turma (Lixeira)
                btn_del = IconRightWidget(icon="trash-can", theme_text_color="Custom", text_color=(0.8,0,0,1))
                btn_del.bind(on_release=lambda x, i=id_t, n=nome_t: self.confirmar_del(i, n))
                item.add_widget(btn_del)

                self.ids.container_turmas.add_widget(item)
                
        except Exception as e:
            print(f"Erro no atualizar: {e}")

    def mostrar_input_turma(self, *args):
        """Cria o diálogo para adicionar nova turma"""
        self.campo = MDTextField(hint_text="Nome da Turma (Ex: 1º Ano A)", mode="rectangle")
        self.d = MDDialog(
            title="Nova Turma",
            type="custom",
            content_cls=self.campo,
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.d.dismiss()),
                MDRaisedButton(
                    text="CRIAR", 
                    md_bg_color=(0.33, 0.42, 0.18, 1), 
                    on_release=self.salvar
                )
            ]
        )
        self.d.open()

    def salvar(self, *a):
        """Salva a nova turma vinculada à disciplina ativa"""
        nome = self.campo.text.strip().upper()
        if nome:
            app = MDApp.get_running_app()
            id_d = getattr(app, 'disciplina_ativa_id', None)
            app.db_manager.salvar_turma(nome, id_d)
            self.atualizar()
            self.d.dismiss()
            toast(f"Turma {nome} cadastrada!")

    def entrar(self, nome, id_t):
        """Entra na turma selecionada"""
        app = MDApp.get_running_app()
        app.turma_ativa = nome
        app.turma_ativa_id = id_t
        try:
            self.manager.current = "chamada_screen"
        except Exception as e:
            print(f"Erro ao mudar de tela: {e}")

    def confirmar_del(self, id_t, nome_t):
        """Diálogo de exclusão de turma"""
        self.d_del = MDDialog(
            title="Excluir Turma?",
            text=f"Deseja remover a turma {nome_t}?\n\nIsso removerá TODOS os alunos, notas, presenças e planejamentos!",
            buttons=[
                MDFlatButton(text="NÃO", on_release=lambda x: self.d_del.dismiss()),
                MDRaisedButton(
                    text="SIM", 
                    md_bg_color=(0.8, 0, 0, 1), 
                    on_release=lambda x: self.deletar_turma(id_t)
                )
            ]
        )
        self.d_del.open()

    def deletar_turma(self, id_t):
        """Deleta a turma - VERSÃO SIMPLES E SEGURA"""
        try:
            app = MDApp.get_running_app()
            
            # Fecha o diálogo
            if hasattr(self, 'd_del') and self.d_del:
                self.d_del.dismiss()
            
            # Exclui a turma
            app.db_manager.excluir_turma(id_t)
            
            # Atualiza a lista
            self.atualizar()
            
            # Mensagem de sucesso
            toast("Turma removida com sucesso!")
            
        except Exception as e:
            print(f"Erro ao deletar turma: {e}")
            toast(f"Erro ao remover turma: {str(e)}")

    def voltar(self):
        self.manager.current = "disciplinas_screen"

# TELA CHAMADA (VERSÃO COM IDENTAÇÃO CORRIGIDA)

from kivy.uix.behaviors import ButtonBehavior


class ClickableLabel(ButtonBehavior, MDLabel):
    """Label clicável para navegação"""
    pass
    
class TelaChamada(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.p_dict = {}  # Presenças (True/False)
        self.j_dict = {}  # Justificativas (Texto)
        from datetime import datetime
        self.data_final_chamada = datetime.now().strftime("%Y-%m-%d")
        self.tema_final_chamada = ""
        self.aulas_planejadas = []
        self.indice_aula_atual = 0
        self.botoes_tri = {}
        self.file_manager = None  # Gerenciador unificado para CSV e Notas
        self.alunos_da_turma = []
        self.lbl_resumo_presenca = None
        self.lbl_aula_atual = None
        self.btn_salvar_banco = None
        self.btn_sincronizar = None
        self.dialogo_plan = None
        self.dialogo_editar_tema = None
        self.novo_campo_tema = None
        self.aula_selecionada_plan = None
        self.data_iso_plan = ""
        self.trimestre_atual_plan = 1

    def on_pre_enter(self):
        """Executado antes de entrar na tela"""
        self.atualizar()

    def atualizar(self):
        """Reconstrói a lista de alunos com controle de presença e exclusão"""
        from kivymd.app import MDApp
        from kivymd.uix.list import TwoLineAvatarIconListItem, IconLeftWidget, IconRightWidget
        
        if 'lista_alunos_chamada' not in self.ids:
            return
        
        self.ids.lista_alunos_chamada.clear_widgets()
        app = MDApp.get_running_app()
        turma_id = getattr(app, 'turma_ativa_id', None)
        
        if not turma_id:
            return

        alunos = app.db_manager.buscar_alunos_por_turma(turma_id)
        self.alunos_da_turma = alunos
        
        # Reinicia dicionários mantendo integridade
        self.p_dict = {aluno['id']: True for aluno in alunos}
        self.j_dict = {aluno['id']: "" for aluno in alunos}

        for aluno in alunos:
            id_a, nome = aluno['id'], aluno['nome']
            
            item = TwoLineAvatarIconListItem(
                text=str(nome).upper(),
                secondary_text="Presente",
                on_release=lambda x, i=id_a, n=nome: self.ir_relatorio(i, n)
            )
            
            # Botão de Presença (Esquerda)
            icone_p = IconLeftWidget(
                icon="check-circle",
                theme_text_color="Custom",
                text_color=(0.33, 0.42, 0.18, 1)
            )
            icone_p.bind(on_release=lambda x, i=id_a, it=item: self.toggle_presenca(i, it))
            
            # Botão de Lixeira (Direita)
            icone_l = IconRightWidget(
                icon="trash-can-outline",
                theme_text_color="Custom",
                text_color=(0.8, 0, 0, 1)
            )
            icone_l.bind(on_release=lambda x, i=id_a, n=nome: self.confirmar_exclusao_aluno(i, n))
            
            item.add_widget(icone_p)
            item.add_widget(icone_l)
            self.ids.lista_alunos_chamada.add_widget(item)

    def ir_relatorio(self, id_aluno, nome_aluno):
        """Abre o relatório do aluno selecionado"""
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        app = MDApp.get_running_app()
        
        # Armazena os dados do aluno ativo
        app.aluno_ativo_id = id_aluno
        app.aluno_ativo_nome = nome_aluno
        
        # Verifica se já temos o nome da turma ativa
        if not hasattr(app, 'turma_ativa_nome') or not app.turma_ativa_nome:
            # Busca o nome da turma no banco de dados
            turma_id = getattr(app, 'turma_ativa_id', None)
            if turma_id:
                turma_nome = app.db_manager.buscar_turma_nome(turma_id)
                app.turma_ativa_nome = turma_nome
            else:
                app.turma_ativa_nome = getattr(app, 'turma_ativa', "Turma")
        
        # Navega para a tela de relatório
        try:
            self.manager.current = "relatorio_screen"
            toast(f"Relatório de {nome_aluno}")
        except Exception as e:
            print(f"Erro ao abrir relatório: {e}")
            toast("Erro ao abrir relatório")

    def toggle_presenca(self, aluno_id, item):
        """Alterna presença com justificativa opcional"""
        self.p_dict[aluno_id] = not self.p_dict[aluno_id]
        status = self.p_dict[aluno_id]
        item.secondary_text = "Presente" if status else "FALTA"
        
        # Atualiza o ícone
        for widget in item.children:
            if hasattr(widget, 'children'):
                for sub in widget.children:
                    if hasattr(sub, 'icon') and 'circle' in sub.icon:
                        sub.icon = "check-circle" if status else "close-circle"
                        sub.text_color = (0.33, 0.42, 0.18, 1) if status else (0.8, 0, 0, 1)
                        break
        
        # Se for falta, abre popup de justificativa
        if not status:
            nome_aluno = self.buscar_nome_aluno(aluno_id)
            self.abrir_popup_justificativa_chamada(aluno_id, nome_aluno)
        
        # Atualiza resumo
        self.atualizar_resumo_dinamico_aula()

    def buscar_nome_aluno(self, aluno_id):
        """Busca o nome do aluno pelo ID"""
        for aluno in self.alunos_da_turma:
            if aluno['id'] == aluno_id:
                return aluno['nome']
        return "Aluno"

    def abrir_popup_justificativa_chamada(self, id_a, nome):
        """Abre diálogo para justificar falta"""
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDRaisedButton
        
        self.campo_j = MDTextField(hint_text="Motivo da falta", mode="rectangle")
        self.diag_j = MDDialog(
            title=f"Justificativa: {nome}",
            type="custom",
            content_cls=self.campo_j,
            buttons=[MDRaisedButton(text="SALVAR", on_release=lambda x: self.gravar_justificativa(id_a))]
        )
        self.diag_j.open()

    def gravar_justificativa(self, id_a):
        """Salva a justificativa da falta"""
        self.j_dict[id_a] = self.campo_j.text
        if hasattr(self, 'diag_j'):
            self.diag_j.dismiss()
        self.atualizar_resumo_dinamico_aula()

    def obter_resumo_presenca(self):
        """Calcula o total de presentes, faltas e justificativas da tela atual"""
        if not hasattr(self, 'p_dict') or not self.p_dict:
            return "Nenhum aluno registrado"
        p = sum(1 for s in self.p_dict.values() if s)
        f = len(self.p_dict) - p
        j = sum(1 for v in self.j_dict.values() if v.strip() != "")
        return f"Resumo Atual da Tela:\n{p} Presenças | {f} Faltas\n({j} Justificadas)"

    # ==================== NAVEGAÇÃO DE AULA E PLANEJAMENTO ====================

    def sincronizar_cores_botoes(self, tri_selecionado):
        """Pinta o botão do trimestre ativo"""
        if hasattr(self, 'botoes_tri'):
            for t, btn in self.botoes_tri.items():
                btn.md_bg_color = (0.33, 0.42, 0.18, 1) if str(t) == str(tri_selecionado) else (0.5, 0.5, 0.5, 1)

    def atualizar_aulas_chamada(self, trimestre):
        """Roda ao clicar nos botões de TRI no popup"""
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        app.trimestre_global = str(trimestre)
        self.sincronizar_cores_botoes(trimestre)
        self.aulas_planejadas = app.db_manager.buscar_planejamentos_por_turma(app.turma_ativa_id, int(trimestre))
        self.indice_aula_atual = 0
        self.mudar_aula(0)

    def mudar_aula(self, direcao):
        """Navega entre as aulas e atualiza o label e o resumo com dados do banco"""
        if not hasattr(self, 'aulas_planejadas') or not self.aulas_planejadas:
            if hasattr(self, 'lbl_aula_atual') and self.lbl_aula_atual:
                self.lbl_aula_atual.text = "Sem aulas no TRI"
            if hasattr(self, 'lbl_resumo_presenca') and self.lbl_resumo_presenca:
                self.lbl_resumo_presenca.text = "Nenhuma aula selecionada"
            self.data_final_chamada = "0000-00-00"
            return
        
        if direcao != 0:
            self.indice_aula_atual += direcao
        self.indice_aula_atual = max(0, min(len(self.aulas_planejadas) - 1, self.indice_aula_atual))
        
        aula = self.aulas_planejadas[self.indice_aula_atual]
        data_res = aula.get('data_aula') or aula.get('data') or "---"
        tema_res = aula.get('titulo') or aula.get('tema') or "Sem Título"
        
        if hasattr(self, 'lbl_aula_atual') and self.lbl_aula_atual:
            self.lbl_aula_atual.text = f"{data_res}\n{tema_res}"
        
        self.data_final_chamada = data_res
        self.tema_final_chamada = tema_res
        
        # Atualiza o label do resumo
        self.atualizar_resumo_dinamico_aula()

    def atualizar_resumo_dinamico_aula(self):
        """Busca no banco o resumo da data mostrada no carrossel/navegador"""
        if not hasattr(self, 'lbl_resumo_presenca') or not self.lbl_resumo_presenca:
            return

        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        data_alvo = getattr(self, 'data_final_chamada', "")
        tema_alvo = getattr(self, 'tema_final_chamada', "")

        if app.db_manager.verificar_presenca_existente(app.turma_ativa_id, data_alvo):
            resumo_banco = app.db_manager.buscar_resumo_aula_salva(app.turma_ativa_id, data_alvo, tema_alvo)
            faltosos = app.db_manager.buscar_nomes_faltosos_aula(app.turma_ativa_id, data_alvo, tema_alvo)
            
            total_f = resumo_banco.get('faltas', 0)
            total_p = resumo_banco.get('presencas', 0)
            
            texto = f"[color=1e3799]Registrado no Banco de Dados:[/color]\n" \
                    f"{total_p} Presentes  |  {total_f} Faltas\n"
            if faltosos:
                texto += f"[size=13sp]Ausentes: {', '.join(faltosos[:3])}{'...' if len(faltosos) > 3 else ''}[/size]"
            
            self.lbl_resumo_presenca.text = texto
        else:
            self.lbl_resumo_presenca.text = f"[color=7f8c8d]Nova Chamada:[/color]\n{self.obter_resumo_presenca()}"

    # ==================== POPUP PRINCIPAL DE CHAMADA ====================
    def abrir_popup_registro_aula(self, *args):
        """Abre o seletor com visual de resumo aprimorado"""
        from kivymd.app import MDApp
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.button import MDIconButton, MDRaisedButton, MDFlatButton
        from kivymd.uix.dialog import MDDialog
        
        app = MDApp.get_running_app()
        self.indice_aula_atual = 0
        self.aulas_planejadas = app.db_manager.buscar_planejamentos_por_turma(
            app.turma_ativa_id,
            int(getattr(app, 'trimestre_global', "1"))
        )
        
        layout = MDBoxLayout(orientation="vertical", spacing="12dp", padding="15dp", size_hint_y=None, height="580dp")
        layout.add_widget(app.gerar_botoes_trimestre(self, self.atualizar_aulas_chamada))
        layout.add_widget(MDLabel(text="Selecione a aula planejada:", halign="center", bold=True, adaptive_height=True))
        
        nav = MDBoxLayout(orientation="horizontal", spacing="5dp", size_hint_y=None, height="80dp")
        btn_esq = MDIconButton(icon="chevron-left", on_release=lambda x: self.mudar_aula(-1))
        
        self.lbl_aula_atual = ClickableLabel(text="Carregando...", halign="center", valign="middle")
        self.lbl_aula_atual.bind(on_release=self.ativar_confirmacao_aula)
        self.lbl_aula_atual.bind(size=self.lbl_aula_atual.setter('text_size'))
        
        btn_dir = MDIconButton(icon="chevron-right", on_release=lambda x: self.mudar_aula(1))
        
        nav.add_widget(btn_esq)
        nav.add_widget(self.lbl_aula_atual)
        nav.add_widget(btn_dir)
        layout.add_widget(nav)
        
        self.lbl_resumo_presenca = MDLabel(
            text="", halign="center", theme_text_color="Primary",
            font_style="Subtitle1", bold=True, markup=True, size_hint_y=None, height="120dp"
        )
        layout.add_widget(self.lbl_resumo_presenca)
        
        self.btn_sincronizar = MDRaisedButton(
            text="SALVAR NA PLANILHA",
            md_bg_color=(0.1, 0.5, 0.1, 1),
            disabled=False,
            on_release=lambda x: MDApp.get_running_app().abrir_seletor_global("CHAMADA_EXEC", ['.xlsx'])
        )
        layout.add_widget(self.btn_sincronizar)
        
        self.dialogo_finalizar = MDDialog(
            title="Finalizar Chamada",
            type="custom",
            content_cls=layout,
            size_hint=(0.95, 0.85),
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialogo_finalizar.dismiss()),
                MDRaisedButton(
                    text="SALVAR CHAMADA",
                    md_bg_color=(0.33, 0.42, 0.18, 1),
                    on_release=self.mostrar_recibo_conferencia
                )
            ]
        )
        self.dialogo_finalizar.open()
        self.sincronizar_cores_botoes(app.trimestre_global)
        self.mudar_aula(0)

    def ativar_confirmacao_aula(self, *args):
        """Habilita salvamento quando uma aula é selecionada manualmente"""
        if hasattr(self, 'btn_salvar_banco') and self.btn_salvar_banco:
            self.btn_salvar_banco.disabled = False
            self.btn_salvar_banco.md_bg_color = (0.33, 0.42, 0.18, 1)

    # ==================== SALVAMENTO E GERENCIAMENTO DE CHAMADA =============
    def mostrar_recibo_conferencia(self, *args):
        """Exibe o resumo detalhado e solicita a confirmação final para salvar"""
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivy.uix.scrollview import ScrollView
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        
        data_sel = getattr(self, 'data_final_chamada', "0000-00-00")
        
        tema_aula = ""
        if hasattr(self, 'lbl_aula_atual') and self.lbl_aula_atual:
            texto_label = self.lbl_aula_atual.text
            tema_aula = texto_label.split('\n')[-1] if '\n' in texto_label else texto_label
        
        presentes = sum(1 for s in self.p_dict.values() if s)
        faltas = len(self.p_dict) - presentes
        
        conteudo = MDBoxLayout(orientation="vertical", spacing="8dp", padding="10dp", size_hint_y=None)
        conteudo.bind(minimum_height=conteudo.setter('height'))

        conteudo.add_widget(MDLabel(
            text=f"[b]CONFERÊNCIA DE LANÇAMENTO[/b]\n[i]{data_sel} - {tema_aula}[/i]",
            markup=True, halign="center", theme_text_color="Primary", size_hint_y=None, height="60dp"
        ))

        conteudo.add_widget(MDLabel(
            text=f"[color=27ae60]Presenças: {presentes}[/color]  |  [color=c0392b]Faltas: {faltas}[/color]",
            markup=True, halign="center", font_style="H6", size_hint_y=None, height="40dp"
        ))

        faltosos_texto = "[b]Revisão de Ausências:[/b]\n"
        tem_falta = False
        for aluno in self.alunos_da_turma:
            if not self.p_dict.get(aluno['id']):
                tem_falta = True
                just = self.j_dict.get(aluno['id'], "")
                motivo = f" ({just})" if just else " [color=ff0000](Sem Justificativa)[/color]"
                faltosos_texto += f"• {aluno['nome'].upper()}{motivo}\n"
        
        if not tem_falta:
            faltosos_texto += "Todos os alunos estão presentes."

        detalhe = MDLabel(text=faltosos_texto, markup=True, theme_text_color="Secondary", size_hint_y=None, halign="left")
        detalhe.bind(texture_size=detalhe.setter('size'))
        
        scroll = ScrollView(size_hint_y=None, height="180dp")
        scroll.add_widget(detalhe)
        conteudo.add_widget(scroll)

        self.dialogo_recibo = MDDialog(
            title="Confirmar Registro?",
            type="custom",
            content_cls=conteudo,
            buttons=[
                MDFlatButton(text="CORRIGIR", on_release=lambda x: self.dialogo_recibo.dismiss()),
                MDRaisedButton(
                    text="CONFIRMAR E SALVAR",
                    md_bg_color=(0.1, 0.4, 0.1, 1),
                    on_release=lambda x: self.confirmar_gravacao_banco(data_sel, tema_aula)
                )
            ]
        )
        self.dialogo_recibo.open()

    def confirmar_gravacao_banco(self, data_sel, tema_aula):
        """Grava dados no banco e libera o botão para enviar à planilha"""
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        app = MDApp.get_running_app()
        trimestre_atual = int(getattr(app, 'trimestre_global', "1"))

        app.db_manager.excluir_presenca_especifica(app.turma_ativa_id, data_sel, tema_aula)

        for id_aluno, presente in self.p_dict.items():
            presenca_bit = 1 if presente else 0
            justificativa = self.j_dict.get(id_aluno, "")
            app.db_manager.salvar_presenca(
                id_aluno, app.turma_ativa_id, data_sel,
                tema_aula, presenca_bit, justificativa, trimestre_atual
            )
        
        if hasattr(self, 'dialogo_recibo') and self.dialogo_recibo:
            self.dialogo_recibo.dismiss()
        
        self.notificar_relatorio_atualizar()
        toast("✅ Chamada registrada com sucesso!")
        
        # 🔓 LIBERA O BOTÃO DE EXPORTAR DA CHAMADA
        # Certifique-se de que o id do seu botão de exportar a chamada no KV seja 'btn_sincronizar_chamada'
        if hasattr(self.ids, 'btn_sincronizar_chamada'):
            self.ids.btn_sincronizar_chamada.disabled = False
        elif hasattr(self, 'btn_sincronizar') and self.btn_sincronizar:
            self.btn_sincronizar.disabled = False
        
        return False

# ==================== SINCRONIZAÇÃO COM PLANILHA ====================

    def processar_planilha_chamada(self, path):
        """
        Recebe a planilha selecionada e abre diálogo para o professor escolher
        qual data e trimestre sincronizar.
        """
        import os
        from kivymd.app import MDApp
        from kivymd.toast import toast
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.button import MDRaisedButton, MDFlatButton
        from kivymd.uix.selectioncontrol import MDCheckbox
        from kivy.uix.scrollview import ScrollView
        from gerenciador_planilha import GerenciadorPlanilha
        from datetime import datetime
        
        app = MDApp.get_running_app()
        
        try:
            app.gerenciador_planilha = GerenciadorPlanilha(path)
            app.caminho_planilha = path
            
            aulas_por_trimestre = {}
            for tri in [1, 2, 3]:
                aulas = app.db_manager.buscar_planejamentos_por_turma(app.turma_ativa_id, tri)
                if aulas:
                    aulas_por_trimestre[tri] = aulas
            
            if not aulas_por_trimestre:
                toast("❌ Nenhuma aula planejada para sincronizar!")
                return
            
            layout = MDBoxLayout(orientation="vertical", spacing="10dp", padding="15dp", size_hint_y=None)
            layout.bind(minimum_height=layout.setter('height'))
            
            layout.add_widget(MDLabel(
                text="[b]SELECIONE A AULA PARA SINCRONIZAR[/b]",
                markup=True,
                halign="center",
                size_hint_y=None,
                height="40dp"
            ))
            
            layout.add_widget(MDLabel(
                text=f"Planilha: {os.path.basename(path)}",
                halign="center",
                theme_text_color="Secondary",
                size_hint_y=None,
                height="30dp"
            ))
            
            scroll = ScrollView(size_hint_y=None, height="350dp")
            container_aulas = MDBoxLayout(orientation="vertical", spacing="8dp", size_hint_y=None)
            container_aulas.bind(minimum_height=container_aulas.setter('height'))
            
            self.checkboxes_aulas = {}
            
            for tri in [1, 2, 3]:
                if tri in aulas_por_trimestre:
                    header = MDLabel(
                        text=f"[b]{tri}º TRIMESTRE[/b]",
                        markup=True,
                        size_hint_y=None,
                        height="30dp",
                        color=(0.33, 0.42, 0.18, 1)
                    )
                    container_aulas.add_widget(header)
                    
                    for aula in aulas_por_trimestre[tri]:
                        data_str = aula.get('data_aula')
                        tema = aula.get('titulo', 'Sem título')
                        
                        try:
                            data_obj = datetime.strptime(data_str, "%Y-%m-%d")
                            data_br = data_obj.strftime("%d/%m/%Y")
                        except:
                            data_br = data_str
                        
                        linha_aula = MDBoxLayout(orientation="horizontal", spacing="10dp", size_hint_y=None, height="50dp")
                        
                        checkbox = MDCheckbox(size_hint_x=None, width="48dp")
                        checkbox.active = False
                        
                        label = MDLabel(
                            text=f"[b]{data_br}[/b]\n{tema[:35]}{'...' if len(tema) > 35 else ''}",
                            markup=True,
                            size_hint_x=0.8
                        )
                        
                        linha_aula.add_widget(checkbox)
                        linha_aula.add_widget(label)
                        
                        self.checkboxes_aulas[f"{tri}|{data_str}"] = {
                            'checkbox': checkbox,
                            'trimestre': tri,
                            'data': data_str,
                            'tema': tema,
                            'data_br': data_br
                        }
                        
                        container_aulas.add_widget(linha_aula)
            
            scroll.add_widget(container_aulas)
            layout.add_widget(scroll)
            
            self.lbl_resumo_sync = MDLabel(
                text="Nenhuma aula selecionada",
                halign="center",
                theme_text_color="Error",
                size_hint_y=None,
                height="40dp",
                markup=True
            )
            layout.add_widget(self.lbl_resumo_sync)
            
            def atualizar_resumo(*args):
                selecionadas = [info for info in self.checkboxes_aulas.values() if info['checkbox'].active]
                if selecionadas:
                    qtd = len(selecionadas)
                    texto = f"[color=27ae60]✅ {qtd} aula(s) selecionada(s)[/color]"
                    self.lbl_resumo_sync.text = texto
                    self.lbl_resumo_sync.theme_text_color = "Custom"
                else:
                    self.lbl_resumo_sync.text = "[color=c0392b]❌ Nenhuma aula selecionada[/color]"
                    self.lbl_resumo_sync.theme_text_color = "Custom"
            
            for info in self.checkboxes_aulas.values():
                info['checkbox'].bind(active=atualizar_resumo)
            
            self.dialogo_sync_chamada = MDDialog(
                title="Sincronizar Chamada",
                type="custom",
                content_cls=layout,
                size_hint=(0.95, 0.9),
                buttons=[
                    MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialogo_sync_chamada.dismiss()),
                    MDRaisedButton(
                        text="SINCRONIZAR",
                        md_bg_color=(0.33, 0.42, 0.18, 1),
                        on_release=lambda x: self._confirmar_sincronizacao_chamada()
                    )
                ]
            )
            self.dialogo_sync_chamada.open()
            
        except Exception as e:
            print(f"❌ Erro ao abrir seletor: {e}")
            import traceback
            traceback.print_exc()
            toast(f"❌ Erro: {str(e)[:40]}")

    def _confirmar_sincronizacao_chamada(self):
        """Confirma e executa a sincronização - Busca faltas do BANCO para cada data"""
        from kivymd.app import MDApp
        from kivymd.toast import toast
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivy.uix.scrollview import ScrollView
        
        print("🔵🔵🔵 _confirmar_sincronizacao_chamada FOI CHAMADO! 🔵🔵🔵")
        
        app = MDApp.get_running_app()
        
        # Coleta as aulas selecionadas
        aulas_selecionadas = []
        for key, info in self.checkboxes_aulas.items():
            if info['checkbox'].active:
                aulas_selecionadas.append(info)
        
        if not aulas_selecionadas:
            toast("❌ Selecione pelo menos uma aula!")
            return
        
        # Busca faltas do BANCO para cada data
        aulas_com_faltas = []
        total_faltas_geral = 0
        
        for aula in aulas_selecionadas:
            faltosos = app.db_manager.buscar_nomes_faltosos_aula(
                app.turma_ativa_id,
                aula['data'],
                aula['tema']
            )
            
            print(f"Aula {aula['data_br']}: {len(faltosos)} faltas no banco")
            
            if faltosos:
                total_faltas_geral += len(faltosos)
                aulas_com_faltas.append({
                    'aula': aula,
                    'faltosos': faltosos,
                    'qtd_faltas': len(faltosos)
                })
        
        # Cria o layout do resumo
        layout_resumo = MDBoxLayout(orientation="vertical", spacing="12dp", padding="15dp", size_hint_y=None)
        layout_resumo.bind(minimum_height=layout_resumo.setter('height'))
        
        layout_resumo.add_widget(MDLabel(
            text="[b]📋 RESUMO DA SINCRONIZAÇÃO[/b]",
            markup=True,
            halign="center",
            size_hint_y=None,
            height="40dp"
        ))
        
        layout_resumo.add_widget(MDLabel(
            text=f"Total de aulas selecionadas: [b]{len(aulas_selecionadas)}[/b]",
            markup=True,
            halign="center",
            size_hint_y=None,
            height="30dp"
        ))
        
        if total_faltas_geral > 0:
            texto_faltas = f"Total de faltas a registrar: [b][color=#cc0000]{total_faltas_geral}[/color][/b]"
        else:
            texto_faltas = f"Total de faltas a registrar: [b][color=#2a6b16]{total_faltas_geral}[/color][/b]"
        
        layout_resumo.add_widget(MDLabel(
            text=texto_faltas,
            markup=True,
            halign="center",
            size_hint_y=None,
            height="30dp"
        ))
        
        layout_resumo.add_widget(MDLabel(text="", size_hint_y=None, height="10dp"))
        
        scroll = ScrollView(size_hint_y=None, height="350dp")
        container_detalhes = MDBoxLayout(orientation="vertical", spacing="15dp", size_hint_y=None)
        container_detalhes.bind(minimum_height=container_detalhes.setter('height'))
        
        for item in aulas_com_faltas:
            card = MDBoxLayout(orientation="vertical", spacing="5dp", size_hint_y=None, padding="10dp")
            card.bind(minimum_height=card.setter('height'))
            
            aula = item['aula']
            faltosos = item['faltosos']
            qtd = item['qtd_faltas']
            
            header = MDLabel(
                text=f"[b]{aula['trimestre']}º TRIMESTRE - {aula['data_br']}[/b]\n{aula['tema'][:40]}",
                markup=True,
                size_hint_y=None,
                height="45dp"
            )
            header.color = (0.33, 0.42, 0.18, 1)
            card.add_widget(header)
            
            if qtd > 0:
                faltas_label = MDLabel(
                    text=f"⚠️ {qtd} falta(s) a registrar:",
                    markup=True,
                    size_hint_y=None,
                    height="25dp",
                    theme_text_color="Custom",
                    text_color=(0.8, 0.2, 0.2, 1)
                )
                card.add_widget(faltas_label)
                
                nomes_texto = ""
                for i, nome in enumerate(faltosos[:10]):
                    nomes_texto += f"  • {nome}\n"
                
                if len(faltosos) > 10:
                    nomes_texto += f"  • ... e mais {len(faltosos) - 10} aluno(s)"
                
                lista_faltas = MDLabel(
                    text=nomes_texto,
                    markup=True,
                    size_hint_y=None,
                    height=min(int(30 * len(faltosos[:10])), 200),
                    theme_text_color="Secondary"
                )
                card.add_widget(lista_faltas)
            
            container_detalhes.add_widget(card)
        
        if not aulas_com_faltas:
            container_detalhes.add_widget(MDLabel(
                text="✅ Todas as aulas selecionadas têm todos os alunos presentes!",
                halign="center",
                size_hint_y=None,
                height="40dp",
                theme_text_color="Custom",
                text_color=(0.33, 0.42, 0.18, 1)
            ))
        
        scroll.add_widget(container_detalhes)
        layout_resumo.add_widget(scroll)
        
        confirm_dialog = MDDialog(
            title="⚠️ CONFIRMAR SINCRONIZAÇÃO",
            type="custom",
            content_cls=layout_resumo,
            size_hint=(0.95, 0.9),
            buttons=[
                MDFlatButton(text="VOLTAR", on_release=lambda x: confirm_dialog.dismiss()),
               MDRaisedButton(
                text="CONFIRMAR E SINCRONIZAR",
                md_bg_color=(0.33, 0.42, 0.18, 1),
                on_release=lambda x: self._executar_sincronizacao_chamada(
        aulas_selecionadas,  # ← passa as aulas selecionadas
        confirm_dialog       # ← passa o diálogo para fechar
    )
),
            ]
        )
        confirm_dialog.open()
        
    def _executar_sincronizacao_chamada(self, aulas_selecionadas, dialog_confirmacao):
        """
        Executa a sincronização - Busca faltas do BANCO para cada data
        """
        from kivymd.app import MDApp
        from kivymd.toast import toast
        from gerenciador_planilha import GerenciadorPlanilha
        
        print("🔴🔴🔴 _executar_sincronizacao_chamada FOI CHAMADO! 🔴🔴🔴")
        print(f"📊 Aulas para sincronizar: {len(aulas_selecionadas)}")
        
        # Fechar o diálogo de confirmação
        dialog_confirmacao.dismiss()
        
        app = MDApp.get_running_app()
        
        # =========================================================
        # ✅ CRIAR O GERENCIADOR SE NÃO EXISTIR
        # =========================================================
        if not hasattr(app, 'gerenciador_planilha') or app.gerenciador_planilha is None:
            try:
                app.gerenciador_planilha = GerenciadorPlanilha(app.caminho_planilha)
                print(f"✅ GerenciadorPlanilha criado: {app.caminho_planilha}")
            except Exception as e:
                toast(f"❌ Erro ao abrir planilha: {str(e)[:40]}")
                return
        
        sucessos = 0
        erros = 0
        
        for aula in aulas_selecionadas:
            try:
                trimestre = aula['trimestre']
                data_aula = aula['data']
                tema_aula = aula['tema']
                
                print(f"\n📝 Sincronizando: {trimestre}º TRI - {data_aula}")
                
                # Busca faltas do BANCO para esta data/tema
                faltosos_banco = app.db_manager.buscar_nomes_faltosos_aula(
                    app.turma_ativa_id,
                    data_aula,
                    tema_aula
                )
                
                print(f"  📊 Faltas no BANCO: {len(faltosos_banco)}")
                
                # Prepara status dos alunos (só faltosos)
                status_alunos = {}
                for nome in faltosos_banco:
                    status_alunos[nome.upper().strip()] = "F"
                    print(f"  ❌ {nome}")
                
                nome_aba = f"{trimestre}º TRIMESTRE"
                
                # Busca a coluna da data
                print(f"  🔍 Buscando data '{data_aula}' na aba '{nome_aba}'...")
                coluna_data = app.gerenciador_planilha.buscar_coluna_por_data(nome_aba, data_aula)
                
                if coluna_data is None:
                    print(f"  ❌ Data {data_aula} não encontrada na planilha!")
                    erros += 1
                    continue
                
                print(f"  ✅ Data encontrada na coluna: {coluna_data}")
                
                sucesso = app.gerenciador_planilha.lancar_frequencia_completa(
                    nome_aba=nome_aba,
                    coluna_alvo=coluna_data,
                    status_alunos=status_alunos,
                    limpar_antes=True
                )
                
                if sucesso:
                    print(f"  ✅ Sincronizado: {len(faltosos_banco)} falta(s)")
                    sucessos += 1
                else:
                    print(f"  ❌ Falha ao sincronizar")
                    erros += 1
                    
            except Exception as e:
                print(f"  ❌ Erro em {aula['data']}: {e}")
                import traceback
                traceback.print_exc()
                erros += 1
        
        print(f"\n📊 RESULTADO: {sucessos} sucessos, {erros} erros")
        
        if sucessos > 0:
            # ✅ SALVAR A PLANILHA (AGORA O GERENCIADOR EXISTE)
            if app.gerenciador_planilha.salvar():
                toast(f"✅ {sucessos} aula(s) sincronizada(s)!")
                if hasattr(self, 'dialogo_sync_chamada'):
                    self.dialogo_sync_chamada.dismiss()
                if hasattr(self, 'notificar_relatorio_atualizar'):
                    self.notificar_relatorio_atualizar()
            else:
                toast("❌ Planilha aberta? Feche e tente novamente.")
        else:
            toast("❌ Nenhuma aula foi sincronizada!")
        
        if erros > 0:
            toast(f"⚠️ {erros} erro(s) na sincronização")


    # ==================== MÉTODO AUXILIAR ====================

    def notificar_relatorio_atualizar(self):
        """Notifica que o relatório precisa ser atualizado."""
        try:
            from kivymd.app import MDApp
            app = MDApp.get_running_app()
            if hasattr(app, 'root') and hasattr(app.root.ids, 'screen_manager'):
                sm = app.root.ids.screen_manager
                if hasattr(sm, 'get_screen'):
                    try:
                        tela_relatorio = sm.get_screen("relatorio_screen")
                        if hasattr(tela_relatorio, 'carregar_dados_completos'):
                            tela_relatorio.carregar_dados_completos()
                    except:
                        pass
        except:
            pass

    # ==================== MÉTODO CORRIGIDO (SEM DUPLICAÇÃO) ====================
    def processar_planilha_planejamento(self, path):
        
        from kivymd.app import MDApp
        from gerenciador_planilha import GerenciadorPlanilha
        from kivymd.toast import toast
        
        app = MDApp.get_running_app()
        try:
            # Alimenta os atributos originais que seu app espera encontrar em memória
            app.gerenciador_planilha = GerenciadorPlanilha(path)
            app.caminho_planilha = path
            
            # ✅ Chama a sincronização
            self.executar_sincronizacao_planilha_planejamento()
        except Exception as e:
            toast(f"❌ Erro ao inicializar planilha: {str(e)[:30]}")

    # ==================== FUNÇÃO ORIGINAL DO BANCO =============
    def executar_sincronizacao_planilha_planejamento(self, *args):
        """
        Sincroniza datas + temas para a planilha Excel
        """
        from kivymd.app import MDApp
        from kivymd.toast import toast
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        import os
        from datetime import datetime
        
        app = MDApp.get_running_app()
        
        if not hasattr(app, 'gerenciador_planilha') or app.gerenciador_planilha is None:
            toast("❌ Nenhuma planilha selecionada!")
            return
        
        # Busca os planejamentos do banco SQLite
        planejamentos = app.db_manager.buscar_planejamentos_por_turma(
            app.turma_ativa_id, self.trimestre_atual_plan
        )
        
        if not planejamentos:
            toast("⚠️ Nenhuma aula planejada neste trimestre")
            return
        
        # Monta a lista para a planilha
        lista_para_planilha = []
        for aula in planejamentos:
            data_str = aula.get('data_aula')
            tema = aula.get('titulo', 'Sem título')
            if data_str:
                lista_para_planilha.append({
                    'data': data_str,
                    'tema': tema
                })
        
        if not lista_para_planilha:
            toast("❌ Nenhuma data válida encontrada")
            return
        
        # Abre a janela de confirmação
        confirm_dialog = MDDialog(
            title="Confirmar sincronização",
            text=f"{len(lista_para_planilha)} aula(s) serão enviadas.\n\n"
                 f"Trimestre: {self.trimestre_atual_plan}º\n"
                 f"Planilha: {os.path.basename(app.gerenciador_planilha.caminho)}",
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: confirm_dialog.dismiss()),
                MDRaisedButton(
                    text="CONFIRMAR", md_bg_color=(0.33, 0.42, 0.18, 1),
                    on_release=lambda x: self._executar_sync_planejamento_confirmado(
                        self.trimestre_atual_plan, lista_para_planilha, confirm_dialog
                    )
                )
            ]
        )
        confirm_dialog.open()

    def _executar_sync_planejamento_confirmado(self, trimestre, lista_planejamentos, dialog):
        """Executa a sincronização física após confirmação"""
        from kivymd.toast import toast
        from kivymd.app import MDApp
        from datetime import datetime
        
        dialog.dismiss()
        app = MDApp.get_running_app()
        
        try:
            # Verifica se o gerenciador existe
            if not hasattr(app, 'gerenciador_planilha') or app.gerenciador_planilha is None:
                toast("❌ Gerenciador de planilha não inicializado")
                return
            
            # Converte para o formato que o gerenciador espera (lista de tuplas)
            lista_convertida = []
            for aula in lista_planejamentos:
                if isinstance(aula, dict):
                    data_str = aula.get('data')
                    tema = aula.get('tema', 'Sem título')
                    if data_str:
                        if isinstance(data_str, str):
                            data_obj = datetime.strptime(data_str, "%Y-%m-%d")
                        else:
                            data_obj = data_str
                        lista_convertida.append((data_obj, tema))
            
            if not lista_convertida:
                toast("❌ Nenhuma data válida para sincronizar")
                return
            
            # Chama o método correto do gerenciador
            sucesso = app.gerenciador_planilha.sincronizar_planejamento(trimestre, lista_convertida)
            
            if sucesso:
                if app.gerenciador_planilha.salvar():
                    toast(f"✅ Planejamento do {trimestre}º trimestre sincronizado!")
                    if hasattr(self, 'dialogo_plan') and self.dialogo_plan:
                        self.dialogo_plan.dismiss()
                else:
                    toast("❌ Planilha aberta? Feche e tente novamente.")
            else:
                toast("❌ Erro na sincronização interna da planilha")
                
        except Exception as e:
            toast(f"❌ Erro: {str(e)[:40]}")
            print(f"Erro crítico: {e}")

    # ==================== MÉTODOS DO PLANEJADOR ====================

    def abrir_planejamento(self, *args):
        """Abre o planejador de aulas para a turma atual"""
        from kivymd.app import MDApp
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDIconButton, MDRaisedButton, MDFlatButton
        from kivymd.uix.label import MDLabel
        from kivymd.uix.textfield import MDTextField
        from kivy.uix.scrollview import ScrollView
        from kivymd.uix.list import MDList
        from kivymd.uix.dialog import MDDialog
        
        app = MDApp.get_running_app()
        self.data_iso_plan = ""
        self.trimestre_atual_plan = int(getattr(app, 'trimestre_global', "1"))
        
        self.layout_plan = MDBoxLayout(orientation="vertical", spacing="10dp", padding="10dp", 
                                        size_hint_y=None, height="580dp")
        
        # Gera botões de trimestre
        layout_tri = app.gerar_botoes_trimestre(self, self.filtrar_trimestre_visual_plan)
        self.layout_plan.add_widget(layout_tri)
        
        layout_input = MDBoxLayout(adaptive_height=True, spacing="10dp")
        btn_cal = MDIconButton(icon="calendar-plus", icon_size="32sp", on_release=self.exibir_calendario_plan)
        self.label_data_plan = MDLabel(text="Escolha a data", theme_text_color="Secondary")
        layout_input.add_widget(btn_cal)
        layout_input.add_widget(self.label_data_plan)
        self.layout_plan.add_widget(layout_input)
        
        self.campo_tema_plan = MDTextField(hint_text="Título/Tema da aula", mode="rectangle")
        self.layout_plan.add_widget(self.campo_tema_plan)
        
        btn_add = MDRaisedButton(
            text="ADICIONAR", md_bg_color=(0.33, 0.42, 0.18, 1),
            size_hint_x=1, on_release=self.salvar_e_atualizar_plan
        )
        self.layout_plan.add_widget(btn_add)
        
        self.scroll_plan = ScrollView(size_hint=(1, 0.55))
        self.lista_visual_plan = MDList()
        self.scroll_plan.add_widget(self.lista_visual_plan)
        self.layout_plan.add_widget(self.scroll_plan)
        
        self.filtrar_trimestre_visual_plan(self.trimestre_atual_plan)
        
        self.dialogo_plan = MDDialog(
            title="Planejador Gabaritus",
            type="custom",
            content_cls=self.layout_plan,
            size_hint=(0.95, 0.85),
            buttons=[
                MDFlatButton(text="FECHAR", on_release=lambda x: self.dialogo_plan.dismiss()),
                MDRaisedButton(
                    text="ATUALIZAR PLANILHA",
                    md_bg_color=(0.1, 0.3, 0.5, 1),
                    on_release=lambda x: app.abrir_seletor_global("PLAN_EXEC", ['.xlsx'])
                ),
            ],
        )
        self.dialogo_plan.open()


    def exibir_calendario_plan(self, *args):
        """Exibe calendário para seleção de data"""
        from kivymd.uix.pickers import MDDatePicker
        date_dialog = MDDatePicker()
        date_dialog.bind(on_save=self.on_save_data_plan)
        date_dialog.open()

    def on_save_data_plan(self, instance, value, date_range):
        """Salva data selecionada"""
        self.data_iso_plan = value.strftime("%Y-%m-%d")
        self.label_data_plan.text = value.strftime("%d/%m/%Y")

    def salvar_e_atualizar_plan(self, *args):
        """Adiciona nova aula ao planejamento"""
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        app = MDApp.get_running_app()
        tema = self.campo_tema_plan.text.strip()
        if self.data_iso_plan and tema:
            app.db_manager.salvar_planejamento(
                self.data_iso_plan, tema, app.turma_ativa_id, self.trimestre_atual_plan
            )
            self.campo_tema_plan.text = ""
            self.filtrar_trimestre_visual_plan(self.trimestre_atual_plan)
            self.notificar_relatorio_atualizar()
            toast("📝 Aula adicionada!")
                # ==================== MÉTODO AUXILIAR ====================

    def notificar_relatorio_atualizar(self):
        """Notifica que o relatório precisa ser atualizado."""
        try:
            from kivymd.app import MDApp
            app = MDApp.get_running_app()
            if hasattr(app, 'root') and hasattr(app.root.ids, 'screen_manager'):
                sm = app.root.ids.screen_manager
                if hasattr(sm, 'get_screen'):
                    try:
                        tela_relatorio = sm.get_screen("relatorio_screen")
                        if hasattr(tela_relatorio, 'atualizar_dados'):
                            tela_relatorio.atualizar_dados()
                    except:
                        pass
        except:
            pass

    def filtrar_trimestre_visual_plan(self, trimestre):
        """Filtra visualização por trimestre no planejamento"""
        from kivymd.app import MDApp
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.button import MDIconButton
        from kivymd.uix.list import OneLineListItem
        
        app = MDApp.get_running_app()
        
        self.trimestre_atual_plan = int(trimestre)
        
        # Atualiza cores dos botões
        if hasattr(self, 'botoes_tri'):
            for t, btn in self.botoes_tri.items():
                btn.md_bg_color = (0.33, 0.42, 0.18, 1) if str(t) == str(trimestre) else (0.5, 0.5, 0.5, 1)
        
        self.lista_visual_plan.clear_widgets()
        aulas = app.db_manager.buscar_planejamentos_por_turma(app.turma_ativa_id, self.trimestre_atual_plan)
        
        if not aulas:
            self.lista_visual_plan.add_widget(OneLineListItem(
                text="Nenhuma aula planejada neste trimestre", theme_text_color="Hint"
            ))
            return
        
        for aula in aulas:
            item_layout = MDBoxLayout(orientation="horizontal", spacing="10dp", size_hint_y=None, height="50dp")
            
            data_aula = aula.get('data_aula', '---')
            titulo_aula = aula.get('titulo', 'Sem título')
            label_info = MDLabel(text=f"[b]{data_aula}[/b]\n{titulo_aula}", markup=True, size_hint_x=0.7)
            
            btn_editar = MDIconButton(
                icon="pencil", icon_size="20sp", theme_text_color="Custom",
                text_color=(0.33, 0.42, 0.18, 1), on_release=lambda x, a=aula: self.editar_tema_lista_plan(a)
            )
            
            btn_excluir = MDIconButton(
                icon="trash-can", icon_size="20sp", theme_text_color="Custom",
                text_color=(0.8, 0, 0, 1), on_release=lambda x, a=aula: self.confirmar_exclusao_aula_plan(a)
            )
            
            item_layout.add_widget(label_info)
            item_layout.add_widget(btn_editar)
            item_layout.add_widget(btn_excluir)
            self.lista_visual_plan.add_widget(item_layout)

    def editar_tema_lista_plan(self, aula):
        """Abre diálogo para editar o tema da aula"""
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        
        self.aula_selecionada_plan = aula
        self.novo_campo_tema = MDTextField(text=aula.get('titulo', ''), hint_text="Novo título da aula", mode="rectangle")
        
        self.dialogo_editar_tema = MDDialog(
            title="Editar Tema da Aula",
            type="custom",
            content_cls=self.novo_campo_tema,
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialogo_editar_tema.dismiss()),
                MDRaisedButton(
                    text="SALVAR", md_bg_color=(0.33, 0.42, 0.18, 1),
                    on_release=self.salvar_edicao_tema_plan())])

    # ==================== GERENCIAMENTO DE ALUNOS ====================

    def abrir_dialogo_aluno(self):
        """Abre diálogo para cadastrar novo aluno"""
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        
        self.campo_nome_aluno = MDTextField(hint_text="NOME COMPLETO", mode="rectangle")
        self.dialogo_novo = MDDialog(
            title="Cadastrar Aluno",
            type="custom",
            content_cls=self.campo_nome_aluno,
            buttons=[
                MDFlatButton(text="VOLTAR", on_release=lambda x: self.dialogo_novo.dismiss()),
                MDRaisedButton(
                    text="SALVAR", md_bg_color=(0.33, 0.42, 0.18, 1),
                    on_release=self.salvar_novo_aluno
                )
            ]
        )
        self.dialogo_novo.open()

    def salvar_novo_aluno(self, *args):
        """Salva novo aluno no banco"""
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        app = MDApp.get_running_app()
        nome = self.campo_nome_aluno.text.strip().upper()
        if nome:
            app.db_manager.salvar_aluno(nome, app.turma_ativa_id)
            self.dialogo_novo.dismiss()
            self.atualizar()
            toast("Aluno cadastrado!")
        else:
            toast("Digite um nome!")

    def confirmar_exclusao_aluno(self, id_a, nome):
        """Confirma exclusão de aluno"""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        
        self.diag_del = MDDialog(
            title=f"Excluir {nome}?",
            text="Dados de notas e faltas serão apagados permanentemente.",
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.diag_del.dismiss()),
                MDRaisedButton(
                    text="EXCLUIR", md_bg_color=(0.8, 0, 0, 1),
                    on_release=lambda x: self.executar_exclusao_aluno(id_a)
                )
            ]
        )
        self.diag_del.open()

    def executar_exclusao_aluno(self, id_a):
        """Remove aluno do banco"""
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        MDApp.get_running_app().db_manager.excluir_aluno(id_a)
        self.diag_del.dismiss()
        self.atualizar()
        toast("Aluno removido com sucesso")

 # ==================== IMPORTAÇÃO DE CSV ====================

    def abrir_gerenciador_csv(self):
        """Abre o seletor de arquivos direto na pasta de Downloads"""
        # Evita recriar o gerenciador se ele já existir
        if not self.file_manager:
            self.file_manager = MDFileManager(
                exit_manager=lambda x: self.file_manager.close(),
                select_path=self.importar_csv,
                ext=['.csv'],
                preview=False
            )
        
        # 📌 Define o caminho inicial focado na pasta de Downloads
        if platform == "android":
            caminho_inicial = "/storage/emulated/0/Download"
        else:
            caminho_inicial = os.path.join(os.path.expanduser("~"), "Downloads")
        
        # 🛡️ Fallback: Se a pasta de Downloads não existir, recua para a raiz/home
        if not os.path.exists(caminho_inicial):
            caminho_inicial = "/storage/emulated/0/" if platform == "android" else os.path.expanduser("~")
            if not os.path.exists(caminho_inicial):
                caminho_inicial = "/"

        self.file_manager.show(caminho_inicial)

    def importar_csv(self, path):
        """Importa alunos CSV usando o mesmo padrão do cadastro manual"""
        import traceback # Mantido aqui para debugar caso dê erro
        
        if self.file_manager:
            self.file_manager.close()
        
        app = MDApp.get_running_app()
        turma_id = app.turma_ativa_id
        
        if not turma_id:
            toast("❌ Erro: Turma não identificada!")
            print("ERRO: app.turma_ativa_id está vazio!")
            return
        
        print(f"📌 Importando para turma ID: {turma_id} (mesmo do cadastro manual)")
        
        try:
            alunos_importados = 0
            with open(path, 'r', encoding='utf-8-sig') as arquivo:
                leitor = csv.reader(arquivo)
                
                # Pula cabeçalho se existir
                primeira_linha = next(leitor, None)
                if primeira_linha and primeira_linha[0].strip().lower() in ['nome', 'aluno', 'alunos']:
                    print(f"📋 Cabeçalho ignorado: {primeira_linha[0]}")
                else:
                    if primeira_linha and primeira_linha[0].strip():
                        nome = primeira_linha[0].strip().upper()
                        if len(nome) >= 2:
                            app.db_manager.salvar_aluno(nome, turma_id)
                            alunos_importados += 1
                
                # Processa o resto das linhas
                for linha in leitor:
                    if not linha or not linha[0].strip():
                        continue
                    
                    nome = linha[0].strip().upper()
                    
                    if len(nome) >= 2 and nome not in ['NOME', 'ALUNO', 'ALUNOS']:
                        app.db_manager.salvar_aluno(nome, turma_id)
                        alunos_importados += 1
                        print(f"  ✅ Importado: {nome}")
            
            if alunos_importados > 0:
                # Se sua classe tiver o método atualizar(), ele será chamado aqui
                if hasattr(self, 'atualizar'):
                    self.atualizar()
                toast(f"✅ {alunos_importados} aluno(s) importado(s)!")
            else:
                toast("⚠️ Nenhum aluno válido encontrado no CSV")
                
        except Exception as e:
            toast(f"❌ Erro ao ler CSV: {str(e)}")
            print(f"Erro detalhado: {e}")
            traceback.print_exc()

    # ==================== DIÁRIO DE BORDO ====================

    def abrir_popup_selecao_diario(self, *args):
        """Popup 'Dois em Um': Seleciona o Trimestre e o Aluno para o Diário"""
        from kivymd.app import MDApp
        from kivymd.uix.list import OneLineListItem, MDList
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivy.uix.scrollview import ScrollView
        from kivymd.uix.label import MDLabel
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        
        app = MDApp.get_running_app()

        layout_principal = MDBoxLayout(orientation="vertical", spacing="10dp", padding="10dp", size_hint_y=None, height="480dp")
        layout_tri = app.gerar_botoes_trimestre(self, self.atualizar_trimestre_no_popup)
        layout_principal.add_widget(layout_tri)
        layout_principal.add_widget(MDLabel(text="Agora escolha o aluno:", halign="center", italic=True, font_style="Caption"))

        lista_container = MDList()
        alunos = app.db_manager.buscar_alunos_por_turma(app.turma_ativa_id)

        if alunos:
            for aluno in alunos:
                id_a = aluno.get('id') if isinstance(aluno, dict) else aluno[0]
                nome_a = aluno.get('nome') if isinstance(aluno, dict) else aluno[1]
                
                item = OneLineListItem(
                    text=str(nome_a),
                    on_release=lambda x, i=id_a, n=nome_a: self.ir_para_diario_especifico(i, n)
                )
                lista_container.add_widget(item)
        else:
            lista_container.add_widget(OneLineListItem(text="Nenhum aluno encontrado"))

        scroll = ScrollView()
        scroll.add_widget(lista_container)
        layout_principal.add_widget(scroll)

        self.dialogo_escolha_aluno = MDDialog(
            title="Trimestre e Diário",
            type="custom",
            content_cls=layout_principal,
            buttons=[MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialogo_escolha_aluno.dismiss())],
        )
        self.dialogo_escolha_aluno.open()
        self.sincronizar_cores_botoes(app.trimestre_global)

    def atualizar_trimestre_no_popup(self, trimestre):
        """Atualiza o trimestre global e as cores sem fechar o popup"""
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        app = MDApp.get_running_app()
        app.trimestre_global = str(trimestre)
        self.sincronizar_cores_botoes(trimestre)
        toast(f"Período alterado para o {trimestre}º Trimestre")

    def ir_para_diario_especifico(self, id_aluno, nome_aluno):
        """Leva os dados do aluno para a TelaDiario"""
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        app.aluno_ativo_id = id_aluno
        app.aluno_nome_atual = nome_aluno
        
        if hasattr(self, 'dialogo_escolha_aluno') and self.dialogo_escolha_aluno:
            self.dialogo_escolha_aluno.dismiss()
            
        self.manager.current = "diario_screen"

    # ==================== CHAMADA (PRESENÇA) ====================

    def preparar_recibo_conferencia(self, *args):
        """Prepara sincronização com planilha - chamado pelo botão SALVAR NA PLANILHA"""
        from kivymd.toast import toast
        from kivymd.app import MDApp
        
        app = MDApp.get_running_app()
        
        if not hasattr(app, 'gerenciador_planilha') or app.gerenciador_planilha is None:
            toast("❌ Nenhuma planilha selecionada!")
            self.abrir_seletor_planilha_sincronismo()
            return
        
        data_aula = getattr(self, 'data_final_chamada', "")
        
        if not data_aula or data_aula == "0000-00-00":
            toast("⚠️ Selecione uma aula válida primeiro!")
            return
        
        faltosos = []
        for aluno in self.alunos_da_turma:
            if not self.p_dict.get(aluno['id'], True):
                faltosos.append(aluno['nome'])
        
        if not faltosos:
            toast("✅ Nenhuma falta registrada. Nada a sincronizar.")
            return
        
        try:
            sucesso = app.gerenciador_planilha.marcar_faltas_por_data(
                int(app.trimestre_global), data_aula, faltosos
            )
            
            if sucesso:
                if app.gerenciador_planilha.salvar():
                    toast(f"✅ {len(faltosos)} falta(s) registradas na planilha!")
                else:
                    toast("❌ Planilha aberta? Feche e tente novamente.")
            else:
                toast(f"❌ Data {data_aula} não encontrada na planilha")
                
        except Exception as e:
            toast(f"❌ Erro: {str(e)[:40]}")


# TELA DIÁRIO DE BORDO

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton
from kivy.properties import DictProperty
from kivy.lang import Builder
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.textfield import MDTextField

class TelaDiario(MDScreen):
    itens_selecionados = DictProperty({'ADMIN': [], 'PEDAG': [], 'COMP': []})
    dialogo_novo = None 
    dialogo_excluir = None
    categoria_atual_aberta = ""

    def on_pre_enter(self):
        """Busca o nome do aluno e limpa rastros do aluno anterior"""
        app = MDApp.get_running_app()
        
        # Tenta todas as variaveis possíveis onde o nome pode estar guardado
        nome_aluno = getattr(app, 'aluno_nome', 
                     getattr(app, 'aluno_nome_atual', 
                     getattr(app, 'aluno_ativo_nome', "Aluno Selecionado")))
        
        self.ids.toolbar_diario.title = f"Diário: {nome_aluno}"
        self.limpar_tela()
        self.popular_itens()

    def popular_itens(self):
        """Popula e garante que os containers comecem invisíveis mas prontos"""
        dados = {
            'admin': ["Atraso", "Falta de Uniforme", "Sem Material"],
            'pedag': ["Não fez a lição", "Participativo", "Dificuldade Concentração"],
            'comp': ["Conversa excessiva", "Conflito com colega", "Respeitoso"]
        }
        
        for cat, itens in dados.items():
            container = self.ids[f"container_{cat}"]
            container.clear_widgets() 
            container.opacity = 0
            container.height = 0
            container.disabled = True # Começa travado para não clicar através do card
            
            for texto in itens:
                self.adicionar_widget_item(cat, texto)

    def adicionar_widget_item(self, categoria, texto):
        """Cria a linha garantindo que o Checkbox seja clicável e nítido"""
        container = self.ids[f"container_{categoria}"]
        
        # Forçamos disabled=False e opacity=1 para os itens filhos aparecerem
        linha = MDBoxLayout(adaptive_height=True, spacing="10dp", padding=[0, "5dp"], opacity=1)
        
        check = MDCheckbox(
            size_hint=(None, None), 
            size=("48dp", "48dp"), # Tamanho maior para facilitar o toque
            active=False,
            disabled=False
        )
        # Normaliza a chave para o dicionário
        chave_dic = 'PEDAG' if 'pedag' in categoria.lower() else categoria.upper()[:5]
        check.bind(active=lambda inst, val: self.atualizar_selecao(chave_dic, texto, val))
        
        label = MDLabel(
            text=texto, 
            theme_text_color="Primary", # Cor nítida
            font_style="Body1",
            halign="left"
        )
        
        btn_del = MDIconButton(
            icon="delete-outline", 
            icon_size="20sp",
            theme_text_color="Custom", 
            text_color=(0.8, 0.2, 0.2, 1)
        )
        btn_del.on_release = lambda: self.confirmar_exclusao_item(container, linha, chave_dic, texto)
        
        linha.add_widget(check)
        linha.add_widget(label)
        linha.add_widget(btn_del)
        container.add_widget(linha)

    def alternar_painel(self, categoria_alvo):
        """Abre a categoria e LIBERA o clique nos itens (disabled=False)"""
        for cat in ['admin', 'pedag', 'comp']:
            cont = self.ids[f"container_{cat}"]
            if cat == categoria_alvo:
                if cont.height > 0:
                    cont.height, cont.opacity, cont.disabled = 0, 0, True
                else:
                    cont.height = cont.minimum_height
                    cont.opacity = 1
                    cont.disabled = False # <--- ISSO DESTRAVA OS CHECKBOXES
            else:
                cont.height, cont.opacity, cont.disabled = 0, 0, True

    def atualizar_selecao(self, cat, texto, ativa):
        chave = 'ADMIN' if 'ADMIN' in cat else 'PEDAG' if 'PEDAG' in cat else 'COMP'
        if ativa:
            if texto not in self.itens_selecionados[chave]:
                self.itens_selecionados[chave].append(texto)
        else:
            if texto in self.itens_selecionados[chave]:
                self.itens_selecionados[chave].remove(texto)

    def abrir_dialogo_novo(self, categoria):
        self.categoria_atual_aberta = categoria
        if not self.dialogo_novo:
            self.campo_novo_item = MDTextField(hint_text="Nome da ocorrência", mode="rectangle")
            self.dialogo_novo = MDDialog(
                title="Novo Item",
                type="custom",
                content_cls=self.campo_novo_item,
                buttons=[
                    MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialogo_novo.dismiss()),
                    MDRaisedButton(
                        text="ADICIONAR", md_bg_color=(0.33, 0.42, 0.18, 1),
                        on_release=lambda x: self.processar_novo_item(self.categoria_atual_aberta)
                    ),
                ],
            )
        self.dialogo_novo.title = f"Novo Item: {categoria.upper()}"
        self.dialogo_novo.open()

    def processar_novo_item(self, categoria):
        texto = self.campo_novo_item.text.strip().upper()
        if texto:
            self.adicionar_widget_item(categoria, texto)
            self.campo_novo_item.text = ""
            self.dialogo_novo.dismiss()
        else:
            self.campo_novo_item.error = True

    def confirmar_exclusao_item(self, container, linha, cat, texto):
        self.dialogo_excluir = MDDialog(
            title="⚠️ Excluir?",
            text=f"Remover '{texto}' da lista?",
            buttons=[
                MDFlatButton(text="NÃO", on_release=lambda x: self.dialogo_excluir.dismiss()),
                MDRaisedButton(
                    text="SIM, EXCLUIR", 
                    md_bg_color=(0.8, 0.2, 0.2, 1),
                    on_release=lambda x: self.executar_remocao(container, linha, cat, texto)
                ),
            ],
        )
        self.dialogo_excluir.open()

    def executar_remocao(self, container, linha, cat, texto):
        container.remove_widget(linha)
        if texto in self.itens_selecionados[cat]:
            self.itens_selecionados[cat].remove(texto)
        self.dialogo_excluir.dismiss()
    def salvar_diario(self):
        """Salva as ocorrências usando o trimestre selecionado no popup anterior"""
        app = MDApp.get_running_app()
        db = app.db_manager
        id_a = getattr(app, 'aluno_ativo_id', None)
        nome_a = getattr(app, 'aluno_nome_atual', "Aluno")
        
        # 1. Monta o texto do relato
        relato_itens = []
        for cat, itens in self.itens_selecionados.items():
            if itens:
                relato_itens.append(f"{cat}: {', '.join(itens)}")
        
        obs_extra = self.ids.campo_obs.text.strip()
        if obs_extra:
            relato_itens.append(f"OBS: {obs_extra}")
            
        texto_para_banco = " | ".join(relato_itens)

        # 2. Rastreio (Logs para o Pydroid)
        print(f"\n>>> SALVANDO NO DIÁRIO <<<")
        print(f"Aluno: {nome_a} (ID: {id_a})")
        
        # 3. Gravação no Banco de Dados
        if id_a and texto_para_banco:
            try:
                # Pegamos o trimestre que o professor escolheu no popup de seleção
                # Se não encontrar nada, assume o 1º TRI como padrão
                tri = int(getattr(app, 'trimestre_global', 1))
                
                db.salvar_ocorrencia(id_a, "DIÁRIO", texto_para_banco, tri)
                
                print(f"✅ SUCESSO: Registro gravado no TRI {tri}")
                
                # Feedback para o professor
                from kivymd.toast import toast
                toast(f"Diário de {nome_a} salvo com sucesso!")
                
            except Exception as e:
                print(f"❌ ERRO NO BANCO: {e}")
                from kivymd.toast import toast
                toast("Erro ao salvar no banco!")
        else:
            from kivymd.toast import toast
            toast("Nada selecionado para salvar.")

        # 4. Limpa os campos e volta para a tela de chamada
        self.limpar_tela()
        self.manager.current = "chamada_screen"

    def limpar_tela(self):
        """Reseta a tela para o próximo uso"""
        self.itens_selecionados = {'ADMIN': [], 'PEDAG': [], 'COMP': []}
        self.ids.campo_obs.text = ""
        for cat in ['admin', 'pedag', 'comp']:
            # Verificamos se o ID existe antes de mexer (evita erros de interface)
            if f"container_{cat}" in self.ids:
                cont = self.ids[f"container_{cat}"]
                cont.height, cont.opacity, cont.disabled = 0, 0, True


# TELA GABARITO

class TelaGabarito(Screen):
    def on_pre_enter(self):
        self.atualizar()

    def atualizar(self):
        self.ids.lista_atividades.clear_widgets()
        app = MDApp.get_running_app()
        
        # PENTE FINO: Usando o ID da turma ativa diretamente para evitar AttributeError
        turma_id = getattr(app, 'turma_ativa_id', None)
        
        if not turma_id:
            return

        atividades = app.db_manager.buscar_atividades_por_turma(turma_id)

        for atv in atividades:
            tag = "REC" if atv['tipo'] == "recuperacao" else "AVAL"
            item = TwoLineAvatarIconListItem(
                text=f"[{tag}] {atv['nome']}",
                secondary_text=f"Trimestre: {atv['trimestre']} | Valor: {atv['valor']} pts"
            )
            item.bind(on_release=lambda x, i=atv['id'], n=atv['nome']: self.notas(i, n))

            self.ids.lista_atividades.add_widget(item)

    def notas(self, i, n):
        app = MDApp.get_running_app()
        app.atividade_ativa_id = i
        app.atividade_ativa_nome = n
        self.manager.current = "lancamento_screen"

    def preparar_geracao_pdf(self, id_atv, nome_atv):
        app = MDApp.get_running_app()
        db = app.db_manager

        # Verifica se há gabarito configurado
        if not getattr(app, 'gabaritos_versoes', None):
            toast("Configure o Gabarito Mestre na engrenagem primeiro!")
            return

        prof = db.buscar_professor()
        if not prof:
            toast("Configure seu perfil de professor nas configurações!")
            return

        turma_id = getattr(app, 'turma_ativa_id', None)
        alunos = db.buscar_alunos_por_turma(turma_id)
        
        if not alunos:
            toast("Adicione alunos a esta turma primeiro!")
            return

        try:
            from gerador_pdf import gerar_folha_com_qrcode
            caminho = gerar_folha_com_qrcode(
                turma=app.turma_ativa,
                escola=prof[3], # Instituição
                disciplina=prof[1], # Matéria
                professor=prof[0], # Nome
                atividade_nome=nome_atv,
                atividade_id=id_atv,
                lista_alunos=alunos,
                gabaritos_versoes=app.gabaritos_versoes
            )
            if caminho:
                toast(f"PDF Gerado para: {app.turma_ativa}")
        except Exception as e:
            print(f"Erro ao gerar PDF: {e}")
            toast("Erro ao processar PDF")

    def abrir_config_gabarito_mestre(self, atv_id, atv_nome):
        app = MDApp.get_running_app()
        app.atividade_ativa_id = atv_id
        app.atividade_ativa_nome = atv_nome
        app.atividade_ativa_turma = app.turma_ativa
        self.manager.current = "config_gabarito_screen"

    def abrir_dialogo_nova_atividade(self):
        lay = MDBoxLayout(orientation="vertical", spacing="8dp", size_hint_y=None, height="280dp")
        self.c_n = MDTextField(hint_text="Título da Atividade", mode="rectangle")
        self.c_v = MDTextField(hint_text="Valor (pts)", text="10.0", input_filter="float", mode="rectangle")
        self.c_t = MDTextField(hint_text="Trimestre (1, 2 ou 3)", text="1", input_filter="int", mode="rectangle")
        
        bx = MDBoxLayout(adaptive_height=True, spacing="10dp", padding=[0, 10, 0, 0])
        self.ck = MDCheckbox(size_hint=(None, None), size=("48dp", "48dp"))
        bx.add_widget(self.ck)
        bx.add_widget(MDLabel(text="É Prova de Recuperação?", theme_text_color="Secondary"))
        
        lay.add_widget(self.c_n)
        lay.add_widget(self.c_v)
        lay.add_widget(self.c_t)
        lay.add_widget(bx)
        
        self.d_nova = MDDialog(
            title="Nova Atividade",
            type="custom",
            content_cls=lay,
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.d_nova.dismiss()),
                MDRaisedButton(text="CRIAR", md_bg_color=(0.33, 0.42, 0.18, 1), on_release=self.salvar_atividade)
            ]
        )
        self.d_nova.open()

    def salvar_atividade(self, *a):
        if not self.c_n.text:
            toast("Dê um nome à atividade!")
            return
            
        app = MDApp.get_running_app()
        tipo = "recuperacao" if self.ck.active else "normal"
        turma_id = getattr(app, 'turma_ativa_id', None)
        
        try:
            app.db_manager.salvar_atividade(
                self.c_n.text, 
                turma_id, 
                float(self.c_v.text or 0), 
                int(self.c_t.text or 1), 
                tipo
            )
            self.atualizar()
            self.d_nova.dismiss()
            toast("Atividade criada!")
        except Exception as e:
            print(f"Erro ao salvar atividade: {e}")
            toast("Erro ao salvar")

    def abrir_dialogo_excluir(self):
        app = MDApp.get_running_app()
        turma_id = getattr(app, 'turma_ativa_id', None)
        atividades = app.db_manager.buscar_atividades_por_turma(turma_id)

        if not atividades:
            toast("Nenhuma atividade para excluir")
            return

        content = MDBoxLayout(orientation="vertical", spacing="5dp", adaptive_height=True, size_hint_y=None)
        content.height = "300dp"
        scroll = ScrollView()
        lista = MDList()
        
        for atv in atividades:
            tag = "REC" if atv['tipo'] == "recuperacao" else "AVAL"
            item = OneLineListItem(
                text=f"[{tag}] {atv['nome']}",
                on_release=lambda x, i=atv['id']: (self.dialogo_excluir.dismiss(), self.conf_del(i))
            )
            lista.add_widget(item)
            
        scroll.add_widget(lista)
        content.add_widget(scroll)

        self.dialogo_excluir = MDDialog(
            title="Escolha a atividade para excluir",
            type="custom",
            content_cls=content,
            buttons=[MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialogo_excluir.dismiss())]
        )
        self.dialogo_excluir.open()

    def conf_del(self, id_atv):
        self.d_del = MDDialog(
            title="Excluir Atividade?",
            text="Isso apagará todas as notas vinculadas. Deseja continuar?",
            buttons=[
                MDFlatButton(text="NÃO", on_release=lambda x: self.d_del.dismiss()),
                MDRaisedButton(text="EXCLUIR", md_bg_color=(0.8, 0, 0, 1), on_release=lambda x: self.deletar(id_atv))
            ]
        )
        self.d_del.open()

    def deletar(self, id_atv):
        MDApp.get_running_app().db_manager.excluir_atividade(id_atv)
        self.d_del.dismiss()
        self.atualizar()
        toast("Atividade removida")

    # ==================== SINCRONIZAÇÃO DE NOTAS ====================

    # Mapeamento de colunas por trimestre
    COLUNAS_NOTAS = {
        1: {  # 1º Trimestre
            'normal': [74, 75, 76, 77, 78],
            'recuperacao': [81, 82, 83]
        },
        2: {  # 2º Trimestre
            'normal': [79, 80, 81, 82, 83],
            'recuperacao': [86, 87, 88]
        },
       3: {  # 3º Trimestre
           'normal': [81, 82, 83, 84, 85, 86],
           'recuperacao': [88, 89, 90]
       }
    }

    def iniciar_sincronizacao_notas(self, *args):
        """
        PONTO DE ENTRADA para sincronizar notas
        """
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        print("🔴 iniciar_sincronizacao_notas FOI CHAMADO!")
        
        app = MDApp.get_running_app()
        
        turma_id = getattr(app, 'turma_ativa_id', None)
        if not turma_id:
            toast("❌ Nenhuma turma selecionada!")
            return
        
        atividades = app.db_manager.buscar_atividades_por_turma(turma_id)
        
        if not atividades:
            toast("❌ Nenhuma atividade cadastrada!")
            return
        
        # Prepara os dados
        dados_sinc = {'notas': []}
        self.trimestre_atual_notas = 1
        
        contadores = {1: {'normal': 0, 'recuperacao': 0}, 
                      2: {'normal': 0, 'recuperacao': 0},
                      3: {'normal': 0, 'recuperacao': 0}}
        
        for atv in atividades:
            trimestre = atv.get('trimestre', 1)
            tipo = atv.get('tipo', 'normal')
            
            cursor = app.db_manager.conn.cursor()
            cursor.execute("""
                SELECT a.nome, n.nota 
                FROM notas n 
                JOIN alunos a ON n.aluno_id = a.id 
                WHERE n.atividade_id = ? AND a.ativo = 1
                ORDER BY a.nome
            """, (atv['id'],))
            notas = cursor.fetchall()
            
            if notas:
                colunas = self.COLUNAS_NOTAS.get(trimestre, {}).get(tipo, [])
                idx = contadores[trimestre][tipo]
                
                if idx < len(colunas):
                    coluna = colunas[idx]
                    contadores[trimestre][tipo] += 1
                    
                    for nome, nota in notas:
                        dados_sinc['notas'].append({
                            'nome': nome,
                            'nota': nota,
                            'coluna': coluna,
                            'trimestre': trimestre
                        })
                    print(f"✅ {atv['nome']} → {trimestre}º TRI {tipo} → Coluna {coluna}")
                else:
                    print(f"⚠️ {atv['nome']}: sem coluna disponível!")
        
        self.dados_sinc_notas = dados_sinc
        
        print(f"📊 Total de notas preparadas: {len(dados_sinc['notas'])}")
        toast(f"✅ {len(dados_sinc['notas'])} notas preparadas!")
        
        self.abrir_seletor_notas()

    def abrir_seletor_notas(self, *args):
        """
        Abre o seletor de planilha para sincronizar notas
        """
        from kivymd.app import MDApp
        MDApp.get_running_app().abrir_seletor_global("NOTAS_EXEC", ['.xlsx'])

    def processar_gravacao_notas(self, path):
        """
        Executa a gravação das notas na planilha
        (Chamado pelo retorno_seletor_global)
        """
        from kivymd.toast import toast
        from kivymd.app import MDApp
        from gerenciador_planilha import GerenciadorPlanilha
        
        print("🔴🔴🔴 processar_gravacao_notas FOI CHAMADO! 🔴🔴🔴")
        
        app = MDApp.get_running_app()
        
        try:
            if not hasattr(self, 'dados_sinc_notas') or not self.dados_sinc_notas:
                toast("❌ Nenhuma nota para sincronizar! Use 'INICIAR SINCRONIZAÇÃO' primeiro.")
                return
            
            print(f"📊 Dados encontrados: {len(self.dados_sinc_notas.get('notas', []))} notas")
            
            # Instancia o gerenciador
            app.gerenciador_planilha = GerenciadorPlanilha(path)
            app.caminho_planilha = path
            
            gp = app.gerenciador_planilha
            sucessos = 0
            
            # Agrupa notas por trimestre e coluna
            notas_por_trimestre_coluna = {}
            for nota in self.dados_sinc_notas['notas']:
                trimestre = nota.get('trimestre', 1)
                coluna = nota.get('coluna', 74)
                key = (trimestre, coluna)
                if key not in notas_por_trimestre_coluna:
                    notas_por_trimestre_coluna[key] = []
                notas_por_trimestre_coluna[key].append((nota['nome'], nota['nota']))
            
            print(f"📊 Grupos a processar: {len(notas_por_trimestre_coluna)}")
            
            for (trimestre, coluna), lista_notas in notas_por_trimestre_coluna.items():
                print(f"📝 {trimestre}º TRI - Coluna {coluna}: {len(lista_notas)} notas")
                if gp.lancar_notas_com_validacao(trimestre, coluna, lista_notas):
                    sucessos += 1
            
            if sucessos > 0:
                if gp.salvar():
                    toast(f"✅ {sucessos} grupo(s) de notas sincronizados!")
                    self.dados_sinc_notas = None
                else:
                    toast("❌ Planilha aberta? Feche e tente novamente.")
            else:
                toast("⚠️ Nenhuma nota foi sincronizada")
                    
        except Exception as e:
            print(f"❌ Erro crítico: {e}")
            import traceback
            traceback.print_exc()
            toast(f"❌ Erro crítico: {str(e)[:30]}")

    def selecionar_atividades_e_sincronizar(self, *args):
        """
        Abre diálogo para selecionar atividades e sincronizar
        """
        from kivymd.app import MDApp
        from kivymd.toast import toast
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.button import MDRaisedButton, MDFlatButton
        from kivymd.uix.selectioncontrol import MDCheckbox
        from kivy.uix.scrollview import ScrollView
        
        app = MDApp.get_running_app()
        
        turma_id = getattr(app, 'turma_ativa_id', None)
        if not turma_id:
            toast("❌ Nenhuma turma selecionada!")
            return
        
        atividades = app.db_manager.buscar_atividades_por_turma(turma_id)
        
        if not atividades:
            toast("❌ Nenhuma atividade cadastrada!")
            return
        
        layout = MDBoxLayout(orientation="vertical", spacing="10dp", padding="15dp", size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        
        layout.add_widget(MDLabel(
            text="[b]SELECIONE AS ATIVIDADES[/b]",
            markup=True,
            halign="center",
            size_hint_y=None,
            height="40dp"
        ))
        
        scroll = ScrollView(size_hint_y=None, height="400dp")
        container = MDBoxLayout(orientation="vertical", spacing="8dp", size_hint_y=None)
        container.bind(minimum_height=container.setter('height'))
        
        self.checkboxes_atividades_temp = {}
        
        for atv in atividades:
            atv_id = atv.get('id')
            atv_nome = atv.get('nome', 'Sem nome')
            atv_valor = atv.get('valor', 0)
            atv_tipo = atv.get('tipo', 'normal')
            atv_trimestre = atv.get('trimestre', 1)
            
            tag = "📝" if atv_tipo == "normal" else "🔄"
            
            linha = MDBoxLayout(orientation="horizontal", spacing="10dp", size_hint_y=None, height="50dp")
            
            checkbox = MDCheckbox(size_hint_x=None, width="48dp")
            checkbox.active = False
            
            label = MDLabel(
                text=f"[b]{tag} {atv_nome}[/b]\n{atv_trimestre}º TRI - {atv_valor} pts",
                markup=True,
                size_hint_x=0.8
            )
            
            linha.add_widget(checkbox)
            linha.add_widget(label)
            
            container.add_widget(linha)
            
            self.checkboxes_atividades_temp[atv_id] = {
                'checkbox': checkbox,
                'id': atv_id,
                'nome': atv_nome,
                'valor': atv_valor,
                'tipo': atv_tipo,
                'trimestre': atv_trimestre
            }
        
        scroll.add_widget(container)
        layout.add_widget(scroll)
        
        self.lbl_resumo_selecao = MDLabel(
            text="[color=c0392b]❌ Nenhuma atividade selecionada[/color]",
            markup=True,
            halign="center",
            size_hint_y=None,
            height="40dp"
        )
        layout.add_widget(self.lbl_resumo_selecao)
        
        def atualizar_resumo(*args):
            selecionadas = [info for info in self.checkboxes_atividades_temp.values() if info['checkbox'].active]
            if selecionadas:
                qtd = len(selecionadas)
                self.lbl_resumo_selecao.text = f"[color=27ae60]✅ {qtd} atividade(s) selecionada(s)[/color]"
            else:
                self.lbl_resumo_selecao.text = "[color=c0392b]❌ Nenhuma atividade selecionada[/color]"
        
        for info in self.checkboxes_atividades_temp.values():
            info['checkbox'].bind(active=atualizar_resumo)
        
        dialog = MDDialog(
            title="Sincronizar Notas",
            type="custom",
            content_cls=layout,
            size_hint=(0.95, 0.85),
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="PREPARAR E SINCRONIZAR",
                    md_bg_color=(0.33, 0.42, 0.18, 1),
                    on_release=lambda x: self._preparar_e_sincronizar(dialog)
                )
            ]
        )
        dialog.open()

    def _preparar_e_sincronizar(self, dialog):
        """
        Prepara os dados das atividades selecionadas e abre o seletor
        """
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        atividades_selecionadas = []
        for atv_id, info in self.checkboxes_atividades_temp.items():
            if info['checkbox'].active:
                atividades_selecionadas.append(info)
        
        if not atividades_selecionadas:
            toast("❌ Selecione pelo menos uma atividade!")
            return
        
        dialog.dismiss()
        
        app = MDApp.get_running_app()
        
        dados_sinc = {'notas': []}
        
        # Contadores por trimestre e tipo
        contadores = {1: {'normal': 0, 'recuperacao': 0}, 
                      2: {'normal': 0, 'recuperacao': 0},
                      3: {'normal': 0, 'recuperacao': 0}}
        
        for atv in atividades_selecionadas:
            trimestre = atv['trimestre']
            tipo = atv['tipo']
            
            cursor = app.db_manager.conn.cursor()
            cursor.execute("""
                SELECT a.nome, n.nota 
                FROM notas n 
                JOIN alunos a ON n.aluno_id = a.id 
                WHERE n.atividade_id = ? AND a.ativo = 1
                ORDER BY a.nome
            """, (atv['id'],))
            notas = cursor.fetchall()
            
            if notas:
                colunas = self.COLUNAS_NOTAS.get(trimestre, {}).get(tipo, [])
                idx = contadores[trimestre][tipo]
                
                if idx < len(colunas):
                    coluna = colunas[idx]
                    contadores[trimestre][tipo] += 1
                    
                    for nome, nota in notas:
                        dados_sinc['notas'].append({
                            'nome': nome,
                            'nota': nota,
                            'coluna': coluna,
                            'trimestre': trimestre
                        })
                    print(f"✅ {atv['nome']} → {trimestre}º TRI {tipo} → Coluna {coluna}")
                else:
                    print(f"⚠️ {atv['nome']}: sem coluna disponível!")
        
        self.dados_sinc_notas = dados_sinc
        
        print(f"📊 Total de notas preparadas: {len(dados_sinc['notas'])}")
        toast(f"✅ {len(dados_sinc['notas'])} notas preparadas!")
        
        self.abrir_seletor_notas()

    def testar_sincronizacao_notas(self, *args):
        """
        Método de teste - prepara TODAS as atividades e abre o seletor
        """
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        print("🔴 testar_sincronizacao_notas FOI CHAMADO!")
        
        app = MDApp.get_running_app()
        
        turma_id = getattr(app, 'turma_ativa_id', None)
        if not turma_id:
            toast("❌ Nenhuma turma selecionada!")
            return
        
        atividades = app.db_manager.buscar_atividades_por_turma(turma_id)
        
        if not atividades:
            toast("❌ Nenhuma atividade cadastrada!")
            return
        
        dados_sinc = {'notas': []}
        contadores = {1: {'normal': 0, 'recuperacao': 0}, 
                      2: {'normal': 0, 'recuperacao': 0},
                      3: {'normal': 0, 'recuperacao': 0}}
        
        for atv in atividades:
            trimestre = atv.get('trimestre', 1)
            tipo = atv.get('tipo', 'normal')
            
            cursor = app.db_manager.conn.cursor()
            cursor.execute("""
                SELECT a.nome, n.nota 
                FROM notas n 
                JOIN alunos a ON n.aluno_id = a.id 
                WHERE n.atividade_id = ? AND a.ativo = 1
                ORDER BY a.nome
            """, (atv['id'],))
            notas = cursor.fetchall()
            
            if notas:
                colunas = self.COLUNAS_NOTAS.get(trimestre, {}).get(tipo, [])
                idx = contadores[trimestre][tipo]
                
                if idx < len(colunas):
                    coluna = colunas[idx]
                    contadores[trimestre][tipo] += 1
                    
                    for nome, nota in notas:
                        dados_sinc['notas'].append({
                            'nome': nome,
                            'nota': nota,
                            'coluna': coluna,
                            'trimestre': trimestre
                        })
        
        self.dados_sinc_notas = dados_sinc
        
        print(f"📊 Total de notas preparadas: {len(dados_sinc['notas'])}")
        toast(f"✅ {len(dados_sinc['notas'])} notas preparadas!")
        
        self.abrir_seletor_notas()

    def abrir_seletor_atividades(self, path):
        """
        Recebe a planilha selecionada e abre diálogo para o professor escolher
        quais atividades sincronizar (similar à chamada)
        """
        import os
        from kivymd.app import MDApp
        from kivymd.toast import toast
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.button import MDRaisedButton, MDFlatButton
        from kivymd.uix.selectioncontrol import MDCheckbox
        from kivy.uix.scrollview import ScrollView
        from gerenciador_planilha import GerenciadorPlanilha
        
        app = MDApp.get_running_app()
        
        try:
            app.gerenciador_planilha = GerenciadorPlanilha(path)
            app.caminho_planilha = path
            
            print(f"✅ Planilha carregada: {path}")
            
            turma_id = getattr(app, 'turma_ativa_id', None)
            if not turma_id:
                toast("❌ Nenhuma turma selecionada!")
                return
            
            atividades = app.db_manager.buscar_atividades_por_turma(turma_id)
            
            if not atividades:
                toast("❌ Nenhuma atividade cadastrada!")
                return
            
            layout = MDBoxLayout(orientation="vertical", spacing="10dp", padding="15dp", size_hint_y=None)
            layout.bind(minimum_height=layout.setter('height'))
            
            layout.add_widget(MDLabel(
                text="[b]SELECIONE AS ATIVIDADES[/b]",
                markup=True,
                halign="center",
                size_hint_y=None,
                height="40dp"
            ))
            
            layout.add_widget(MDLabel(
                text=f"Planilha: {os.path.basename(path)}",
                halign="center",
                theme_text_color="Secondary",
                size_hint_y=None,
                height="30dp"
            ))
            
            scroll = ScrollView(size_hint_y=None, height="400dp")
            container = MDBoxLayout(orientation="vertical", spacing="8dp", size_hint_y=None)
            container.bind(minimum_height=container.setter('height'))
            
            self.checkboxes_atividades = {}
            
            for atv in atividades:
                atv_id = atv.get('id')
                atv_nome = atv.get('nome', 'Sem nome')
                atv_valor = atv.get('valor', 0)
                atv_tipo = atv.get('tipo', 'normal')
                atv_trimestre = atv.get('trimestre', 1)
                
                tag = "📝" if atv_tipo == "normal" else "🔄"
                
                linha = MDBoxLayout(orientation="horizontal", spacing="10dp", size_hint_y=None, height="50dp")
                
                checkbox = MDCheckbox(size_hint_x=None, width="48dp")
                checkbox.active = False
                
                label = MDLabel(
                    text=f"[b]{tag} {atv_nome}[/b]\n{atv_trimestre}º TRI - {atv_valor} pts",
                    markup=True,
                    size_hint_x=0.8
                )
                
                linha.add_widget(checkbox)
                linha.add_widget(label)
                
                container.add_widget(linha)
                
                self.checkboxes_atividades[atv_id] = {
                    'checkbox': checkbox,
                    'id': atv_id,
                    'nome': atv_nome,
                    'trimestre': atv_trimestre,
                    'valor': atv_valor,
                    'tipo': atv_tipo
                }
            
            scroll.add_widget(container)
            layout.add_widget(scroll)
            
            self.lbl_resumo_notas = MDLabel(
                text="[color=c0392b]❌ Nenhuma atividade selecionada[/color]",
                markup=True,
                halign="center",
                size_hint_y=None,
                height="40dp"
            )
            layout.add_widget(self.lbl_resumo_notas)
            
            def atualizar_resumo(*args):
                selecionadas = [info for info in self.checkboxes_atividades.values() if info['checkbox'].active]
                if selecionadas:
                    qtd = len(selecionadas)
                    self.lbl_resumo_notas.text = f"[color=27ae60]✅ {qtd} atividade(s) selecionada(s)[/color]"
                else:
                    self.lbl_resumo_notas.text = "[color=c0392b]❌ Nenhuma atividade selecionada[/color]"
            
            for info in self.checkboxes_atividades.values():
                info['checkbox'].bind(active=atualizar_resumo)
            
            self.dialogo_sync_atividades = MDDialog(
                title="Sincronizar Notas",
                type="custom",
                content_cls=layout,
                size_hint=(0.95, 0.9),
                buttons=[
                    MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialogo_sync_atividades.dismiss()),
                    MDRaisedButton(
                        text="SINCRONIZAR",
                        md_bg_color=(0.33, 0.42, 0.18, 1),
                        on_release=lambda x: self._confirmar_sincronizacao_notas()
                    )
                ]
            )
            self.dialogo_sync_atividades.open()
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            toast(f"❌ Erro: {str(e)[:40]}")

    def _confirmar_sincronizacao_notas(self):
        """
        Confirma e executa a sincronização das atividades selecionadas
        (Distribuição automática das colunas)
        """
        from kivymd.app import MDApp
        from kivymd.toast import toast
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        
        app = MDApp.get_running_app()
        
        # Coleta as atividades selecionadas
        atividades_selecionadas = []
        for atv_id, info in self.checkboxes_atividades.items():
            if info['checkbox'].active:
                atividades_selecionadas.append(info)
        
        if not atividades_selecionadas:
            toast("❌ Selecione pelo menos uma atividade!")
            return
        
        # Separa por trimestre e tipo
        normais_por_trimestre = {1: [], 2: [], 3: []}
        recuperacoes_por_trimestre = {1: [], 2: [], 3: []}
        
        for atv in atividades_selecionadas:
            tri = atv['trimestre']
            if atv['tipo'] == 'normal':
                normais_por_trimestre[tri].append(atv)
            else:
                recuperacoes_por_trimestre[tri].append(atv)
        
        # Prepara as atividades com suas colunas
        atividades_com_coluna = []
        
        for tri in [1, 2, 3]:
            # Normais
            colunas_normais = self.COLUNAS_NOTAS.get(tri, {}).get('normal', [])
            for idx, atv in enumerate(normais_por_trimestre[tri]):
                if idx < len(colunas_normais):
                    atividades_com_coluna.append({
                        'atividade': atv,
                        'coluna': colunas_normais[idx]
                    })
            
            # Recuperações
            colunas_rec = self.COLUNAS_NOTAS.get(tri, {}).get('recuperacao', [])
            for idx, atv in enumerate(recuperacoes_por_trimestre[tri]):
                if idx < len(colunas_rec):
                    atividades_com_coluna.append({
                        'atividade': atv,
                        'coluna': colunas_rec[idx]
                    })
        
        if not atividades_com_coluna:
            toast("❌ Não há colunas disponíveis!")
            return
        
        # Busca as notas
        atividades_com_notas = []
        total_notas = 0
        
        for item in atividades_com_coluna:
            atv = item['atividade']
            coluna = item['coluna']
            
            cursor = app.db_manager.conn.cursor()
            cursor.execute("""
                SELECT a.nome, n.nota 
                FROM notas n 
                JOIN alunos a ON n.aluno_id = a.id 
                WHERE n.atividade_id = ? AND a.ativo = 1
                ORDER BY a.nome
            """, (atv['id'],))
            notas_banco = cursor.fetchall()
            
            if notas_banco:
                total_notas += len(notas_banco)
                atividades_com_notas.append({
                    'atividade': atv,
                    'coluna': coluna,
                    'notas': notas_banco,
                    'qtd_notas': len(notas_banco)
                })
        
        if total_notas == 0:
            toast("⚠️ Nenhuma nota encontrada!")
            return
        
        # Fecha o diálogo de seleção
        if hasattr(self, 'dialogo_sync_atividades'):
            self.dialogo_sync_atividades.dismiss()
        
        # Popup de confirmação
        layout_resumo = MDBoxLayout(orientation="vertical", spacing="12dp", padding="15dp", size_hint_y=None)
        layout_resumo.bind(minimum_height=layout_resumo.setter('height'))
        
        layout_resumo.add_widget(MDLabel(
            text="[b]📋 RESUMO DA SINCRONIZAÇÃO[/b]",
            markup=True,
            halign="center",
            size_hint_y=None,
            height="40dp"
        ))
        
        for item in atividades_com_notas:
            atv = item['atividade']
            coluna = item['coluna']
            qtd = item['qtd_notas']
            letra = app.gerenciador_planilha._get_column_letter(coluna)
            tipo = "📝 NORMAL" if atv['tipo'] == 'normal' else "🔄 RECUPERAÇÃO"
            
            layout_resumo.add_widget(MDLabel(
                text=f"• {atv['trimestre']}º TRI - {tipo}\n   [b]{atv['nome']}[/b]\n   Coluna {letra} ({coluna}) - {qtd} nota(s)",
                markup=True,
                size_hint_y=None,
                height="55dp"
            ))
        
        layout_resumo.add_widget(MDLabel(
            text=f"\n[b]Total de notas: {total_notas}[/b]",
            markup=True,
            halign="center",
            size_hint_y=None,
            height="40dp",
            color=(0.33, 0.42, 0.18, 1)
        ))
        
        confirm_dialog = MDDialog(
            title="⚠️ CONFIRMAR SINCRONIZAÇÃO",
            type="custom",
            content_cls=layout_resumo,
            size_hint=(0.95, 0.8),
            buttons=[
                MDFlatButton(text="VOLTAR", on_release=lambda x: confirm_dialog.dismiss()),
                MDRaisedButton(
                    text="SINCRONIZAR",
                    md_bg_color=(0.33, 0.42, 0.18, 1),
                    on_release=lambda x: self._executar_sincronizacao_notas(atividades_com_notas, confirm_dialog)
                )
            ]
        )
        confirm_dialog.open()
        
    def _executar_sincronizacao_notas(self, atividades_com_notas, dialog_confirmacao):
        """
        Executa a sincronização das notas na planilha
        PRESERVA FÓRMULAS - só escreve onde é seguro
        """
        from kivymd.app import MDApp
        from kivymd.toast import toast
        
        print("🔴🔴🔴 _executar_sincronizacao_notas FOI CHAMADO! 🔴🔴🔴")
        print(f"📊 Atividades para sincronizar: {len(atividades_com_notas)}")
        
        # Mostra detalhes das atividades
        for item in atividades_com_notas:
            atv = item['atividade']
            coluna = item['coluna']
            qtd = len(item['notas'])
            print(f"  - {atv['trimestre']}º TRI - {atv['nome']} → Coluna {coluna} ({qtd} notas)")
        
        dialog_confirmacao.dismiss()
        app = MDApp.get_running_app()
        
        # DIAGNÓSTICO: Verifica o gerenciador
        print(f"🔍 app.gerenciador_planilha: {app.gerenciador_planilha}")
        print(f"🔍 app.caminho_planilha: {app.caminho_planilha}")
        
        if not hasattr(app, 'gerenciador_planilha') or app.gerenciador_planilha is None:
            toast("❌ Nenhuma planilha selecionada!")
            print("❌ ERRO: gerenciador_planilha é None!")
            return
        
        # =========================================================
        # COLUNAS QUE TÊM FÓRMULAS (NÃO ESCREVER)
        # =========================================================
        COLUNAS_COM_FORMULA = {
            1: [80],      # 1º Trimestre
            2: [84, 85],  # 2º Trimestre (CF e CG)
            3: [87, 89]   # 3º Trimestre
        }
        
        sucessos = 0
        erros = 0
        
        for item in atividades_com_notas:
            try:
                atv = item['atividade']
                trimestre = atv['trimestre']
                coluna = item['coluna']
                notas = item['notas']
                
                print(f"\n📝 Sincronizando: {trimestre}º TRI - {atv['nome']}")
                print(f"  🎯 Coluna: {coluna}")
                print(f"  📊 {len(notas)} notas")
                
                # ✅ VERIFICA SE A COLUNA É BLOQUEADA (TEM FÓRMULA)
                if coluna in COLUNAS_COM_FORMULA.get(trimestre, []):
                    print(f"  ❌ Coluna {coluna} tem fórmula! Não é possível escrever notas aqui.")
                    toast(f"⚠️ {atv['nome']}: coluna {coluna} tem fórmula!")
                    erros += 1
                    continue
                
                # Verifica se a aba existe
                nome_aba = f"{trimestre}º TRIMESTRE"
                print(f"  📑 Verificando aba: {nome_aba}")
                
                # Tenta acessar a aba
                ws = app.gerenciador_planilha._obter_aba(trimestre)
                if ws is None:
                    print(f"  ❌ Aba {nome_aba} não encontrada!")
                    erros += 1
                    continue
                else:
                    print(f"  ✅ Aba encontrada")
                
                # Tenta escrever as notas
                sucesso = app.gerenciador_planilha.lancar_notas_com_validacao(
                    num_trimestre=trimestre,
                    coluna_alvo=coluna,
                    lista_notas=notas
                )
                
                if sucesso:
                    print(f"  ✅ Sincronizado com sucesso")
                    sucessos += 1
                else:
                    print(f"  ❌ Falha ao sincronizar")
                    erros += 1
                    
            except Exception as e:
                print(f"  ❌ Erro em {atv['nome']}: {e}")
                import traceback
                traceback.print_exc()
                erros += 1
        
        print(f"\n📊 RESULTADO: {sucessos} sucessos, {erros} erros")
        
        # ✅ SALVA MESMO SE HOUVER ALGUNS ERROS (desde que tenha sucessos)
        if sucessos > 0:
            try:
                # Verifica se a planilha não está aberta
                if hasattr(app.gerenciador_planilha, 'verificar_planilha_fechada'):
                    if not app.gerenciador_planilha.verificar_planilha_fechada():
                        toast("⚠️ Feche a planilha no Excel antes de salvar!")
                        print("⚠️ Planilha aberta, não é seguro salvar!")
                        return
                
                if app.gerenciador_planilha.salvar():
                    toast(f"✅ {sucessos} atividade(s) sincronizada(s)!")
                    if hasattr(self, 'dialogo_sync_atividades'):
                        self.dialogo_sync_atividades.dismiss()
                else:
                    toast("❌ Planilha aberta? Feche e tente novamente.")
                    print("❌ Falha no salvamento!")
            except Exception as e:
                print(f"❌ Erro ao salvar: {e}")
                toast(f"❌ Erro ao salvar: {str(e)[:30]}")
        else:
            toast("❌ Nenhuma atividade foi sincronizada!")
            print("❌ NENHUMA ATIVIDADE FOI SINCRONIZADA")


     #TELA GABARITO MESTRE
        
class TelaConfigGabarito(Screen):
    gabaritos = DictProperty({})

    def on_pre_enter(self):
        self.carregar_gabarito_existente()

    def carregar_gabarito_existente(self):
        app = MDApp.get_running_app()
        from gerador_pdf import normalizar
        caminho_base = "/storage/emulated/0/Documents/AppProfessor_Turmas" if platform == 'android' else "AppProfessor_Turmas"
        nome_pasta = f"ATV_{app.atividade_ativa_id}_{normalizar(app.atividade_ativa_nome)}"
        pasta_atividade = os.path.join(caminho_base, normalizar(app.atividade_ativa_turma), nome_pasta)
        caminho_json = os.path.join(pasta_atividade, f"gabarito_ID_{app.atividade_ativa_id}.json")

        if os.path.exists(caminho_json):
            with open(caminho_json, 'r') as f:
                self.gabaritos = json.load(f)
            final_text = ""
            for letra, seq in self.gabaritos.items():
                final_text += f"VERSÃO {letra}: {seq}\n"
            self.ids.area_conferencia.text = final_text
            self.ids.qtd_questoes.text = str(len(self.gabaritos['A']))
            self.ids.campo_mestre.text = self.gabaritos['A']
            self.ids.btn_gerar_pdf.disabled = False
            app.gabaritos_versoes = self.gabaritos
            toast("Gabarito carregado - NÃO regenere se já imprimiu!")
        else:
            self.ids.area_conferencia.text = "Versões A, B, C e D aparecerão aqui..."
            self.ids.btn_gerar_pdf.disabled = True

    def validar_texto(self, instance):
        instance.text = instance.text.upper().replace(" ", "")

    def gerar_e_exibir(self):
        if self.gabaritos and 'A' in self.gabaritos:
            self.dialogo = MDDialog(
                title="ATENÇÃO!",
                text="Já existe um gabarito. Gerar novo vai invalidar os cartões impressos. Continuar?",
                buttons=[
                    MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialogo.dismiss()),
                    MDRaisedButton(text="SIM, GERAR NOVO", md_bg_color=(0.8,0,0,1), on_release=lambda x: (self.dialogo.dismiss(), self._gerar_novo()))
                ]
            )
            self.dialogo.open()
        else:
            self._gerar_novo()

    def _gerar_novo(self):
        mestre = self.ids.campo_mestre.text.upper().strip()
        try:
            qtd = int(self.ids.qtd_questoes.text)
        except:
            toast("Qtd inválida")
            return

        if len(mestre)!= qtd:
            toast(f"Esperado {qtd} letras")
            return

        res_base = list(mestre)
        final_text = ""
        temp_gabs = {}

        for letra in ['A', 'B', 'C', 'D']:
            temp_res = res_base[:]
            if letra!= 'A':
                random.shuffle(temp_res)
            str_res = "".join(temp_res)
            temp_gabs[letra] = str_res
            final_text += f"VERSÃO {letra}: {str_res}\n"

        self.gabaritos = temp_gabs
        self.ids.area_conferencia.text = final_text
        self.ids.btn_gerar_pdf.disabled = False
        MDApp.get_running_app().gabaritos_versoes = temp_gabs
        toast("Gabarito gerado! Imprima e não gere novamente.")

    def acao_gerar_pdf(self):
        app = MDApp.get_running_app()
        prof = app.db_manager.buscar_professor()
        turma_id = app.db_manager.buscar_turma_id(app.atividade_ativa_turma)
        alunos = app.db_manager.buscar_alunos_por_turma(turma_id)

        if not alunos:
            toast(f"Sem alunos na turma!")
            return

        try:
            from gerador_pdf import normalizar, gerar_folha_com_qrcode
            caminho_base = "/storage/emulated/0/Documents/AppProfessor_Turmas" if platform == 'android' else "AppProfessor_Turmas"
            nome_pasta = f"ATV_{app.atividade_ativa_id}_{normalizar(app.atividade_ativa_nome)}"
            pasta_atividade = os.path.join(caminho_base, normalizar(app.atividade_ativa_turma), nome_pasta)
            os.makedirs(pasta_atividade, exist_ok=True)

            caminho_json = os.path.join(pasta_atividade, f"gabarito_ID_{app.atividade_ativa_id}.json")
            with open(caminho_json, 'w', encoding='utf-8') as f:
                json.dump(self.gabaritos, f, ensure_ascii=False, indent=4)

            gerar_folha_com_qrcode(
                turma=app.atividade_ativa_turma,
                escola=prof[3] if prof else "Escola",
                disciplina=prof[1] if prof else "Matéria",
                professor=prof[0] if prof else "Professor",
                atividade_nome=app.atividade_ativa_nome,
                atividade_id=app.atividade_ativa_id,
                lista_alunos=alunos,
                gabaritos_versoes=self.gabaritos
            )
            toast(f"PDF salvo!")
        except Exception as e:
            print(f"Erro PDF: {e}")
            toast(f"Erro: {str(e)}")
    
    def voltar(self):
        self.manager.current = "gabarito_screen"
        
        
        
   # TELA LANÇAMENTO DE NOTAS

from kivymd.uix.screen import Screen
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.toast import toast

class TelaLancamentoNotas(MDScreen): # Use MDScreen para manter o padrão KivyMD
    def on_pre_enter(self):
        self.atualizar()

    def atualizar(self):
        self.ids.container_alunos_notas.clear_widgets()
        app = MDApp.get_running_app()
        db = app.db_manager

        # Busca o valor máximo da atividade
        cursor = db.conn.cursor()
        cursor.execute("SELECT valor FROM atividades WHERE id = ?", (app.atividade_ativa_id,))
        res = cursor.fetchone()
        self.valor_maximo = float(res[0]) if res else 10.0

        turma_id = getattr(app, 'turma_ativa_id', None)
        if not turma_id:
            return

        alunos = db.buscar_alunos_por_turma(turma_id)
        
        # Invertemos a ordem da lista para que ao percorrer os .children 
        # no salvar_notas_lote, a lógica faça mais sentido visualmente
        for aluno in alunos:
            id_a = aluno['id']
            nome = str(aluno['nome']).upper() # Mantendo seu padrão de Caixa Alta
            
            nota = db.buscar_nota_aluno(id_a, app.atividade_ativa_id)
            
            box = MDBoxLayout(adaptive_height=True, padding="10dp", spacing="10dp")
            
            box.add_widget(MDLabel(
                text=nome, 
                size_hint_x=0.5,
                font_style="Subtitle2"
            ))

            txt = MDTextField(
                text=str(nota if nota is not None else ""),
                size_hint_x=0.3,
                input_filter="float",
                hint_text="Nota",
                mode="rectangle",
                line_color_focus=(0.33, 0.42, 0.18, 1),
                helper_text=f"Máx: {self.valor_maximo}",
                helper_text_mode="on_focus"
            )
            txt.aluno_id = id_a 
            box.add_widget(txt)

            box.add_widget(MDLabel(
                text=f"/ {self.valor_maximo:.1f}",
                size_hint_x=0.2,
                theme_text_color="Secondary"
            ))

            self.ids.container_alunos_notas.add_widget(box)

    def salvar_notas_lote(self):
        """Validação rigorosa: Só salva se TODOS os campos estiverem corretos"""
        app = MDApp.get_running_app()
        db = app.db_manager
        from kivymd.toast import toast
        
        pode_salvar = True
        lista_para_salvar = [] # Temporário para guardar os dados validados

                # 1ª PASSADA: Verificação de Erros (Mínimo, Máximo e Formato)
        for box in self.ids.container_alunos_notas.children:
            for w in box.children:
                if isinstance(w, MDTextField):
                    try:
                        # Limpa a entrada: troca vírgula por ponto e remove espaços
                        v_txt = w.text.replace(',', '.').strip()
                        
                        if v_txt:
                            v = float(v_txt) # Converte para float (trata notação científica se houver)
                            
                            # TRAVA 1: Nota Maior que o permitido
                            if v > self.valor_maximo:
                                w.error = True
                                w.helper_text = f"Máximo: {self.valor_maximo}"
                                pode_salvar = False
                            
                            # TRAVA 2: Nota Negativa
                            elif v < 0:
                                w.error = True
                                w.helper_text = "A nota não pode ser negativa!"
                                pode_salvar = False
                            
                            # TUDO OK
                            else:
                                w.error = False
                                # Arredonda para 2 casas decimais para evitar dízimas infinitas
                                valor_limpo = round(v, 2)
                                lista_para_salvar.append((w.aluno_id, valor_limpo))
                        else:
                            # Campo vazio vira zero
                            w.error = False
                            lista_para_salvar.append((w.id_aluno, 0.0))
                            
                    except ValueError:
                        # Se o professor digitar algo que não seja número (ex: "falta")
                        w.error = True
                        w.helper_text = "Digite apenas números!"
                        pode_salvar = False

        # 2ª PASSADA: Ação baseada na validação
        if not pode_salvar:
            toast("⚠️ Corrija as notas em vermelho antes de salvar!")
            return # Sai da função sem tocar no banco de dados

        # 3ª PASSADA: Se chegou aqui, está tudo OK. Salva em lote.
        for aluno_id, nota_final in lista_para_salvar:
            db.salvar_nota_final(aluno_id, app.atividade_ativa_id, nota_final)

        toast("✅ Sucesso! Todas as notas foram gravadas.")
        self.manager.current = "gabarito_screen"

# TELA RELATÓRIO

from kivymd.uix.screen import MDScreen
from kivymd.uix.list import TwoLineListItem, OneLineListItem
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList
from kivymd.uix.scrollview import ScrollView
from kivy.uix.behaviors import ButtonBehavior
from kivymd.app import MDApp
from kivymd.toast import toast
from datetime import datetime
import os
import platform
import traceback

class TelaRelatorio(MDScreen):

    def on_pre_enter(self):
        """Prepara a tela ao entrar - SEMPRE busca dados frescos"""
        self.limpar_paineis()
        self.carregar_dados_completos()

    def limpar_paineis(self):
        """Fecha as sanfonas (acordeão) visualmente"""
        for i in range(1, 4):
            id_c = f"container_tri{i}"
            if id_c in self.ids:
                cont = self.ids[id_c]
                cont.height, cont.opacity, cont.disabled = 0, 0, True

    def alternar_painel(self, categoria_alvo):
        """Mecânica de abrir/fechar os trimestres"""
        for cat in ['tri1', 'tri2', 'tri3']:
            id_c = f"container_{cat}"
            if id_c in self.ids:
                cont = self.ids[id_c]
                if cat == categoria_alvo:
                    if cont.height > 0:
                        cont.height, cont.opacity, cont.disabled = 0, 0, True
                    else:
                        cont.height = cont.minimum_height
                        cont.opacity, cont.disabled = 1, False
                else:
                    cont.height, cont.opacity, cont.disabled = 0, 0, True

    def carregar_dados_completos(self):
        """Carrega todas as informações do aluno na interface"""
        print("\n>>> INICIANDO CARREGAMENTO DO RELATÓRIO <<<")
        app = MDApp.get_running_app()
        db = app.db_manager
        id_a = app.aluno_ativo_id
        turma_id = getattr(app, 'turma_ativa_id', None)

        if not id_a:
            print("⚠️ Erro: Nenhum aluno ativo selecionado.")
            return

        # Limpeza de Widgets Antigos
        for i in range(1, 4):
            if f"container_tri{i}" in self.ids:
                self.ids[f"container_tri{i}"].clear_widgets()

        # Cabeçalho
        nome_aluno = getattr(app, 'aluno_ativo_nome', 'Estudante')
        self.ids.lbl_nome_aluno_topo.text = str(nome_aluno).upper()

        # ⭐ Dashboard anual
        soma_total_ano = 0
        total_faltas_ano = 0
        total_planejado_ano = 0
        total_presencas_ano = 0

        # Loop por Trimestre
        for i in range(1, 4):
            target = self.ids[f"container_tri{i}"]

            # --- NOTAS (mantém igual) ---
            notas = db.buscar_notas_individuais_trimestre(id_a, i, "normal")
            for nome, valor in notas:
                target.add_widget(TwoLineListItem(
                    text=f"Avaliação: {nome}",
                    secondary_text=f"Nota: {valor:.1f}"
                ))

            # --- NOTAS DE RECUPERAÇÃO ---
            notas_rec = db.buscar_notas_individuais_trimestre(id_a, i, "recuperacao")
            for nome, valor in notas_rec:
                target.add_widget(TwoLineListItem(
                    text=f"Recuperação: {nome}",
                    secondary_text=f"Nota: {valor:.1f}",
                    theme_text_color="Custom",
                    text_color=(0.8, 0.5, 0, 1)
                ))

            # --- FECHAMENTO ACADÊMICO ---
            res = db.buscar_dados_trimestre(id_a, turma_id, i)
            if res:
                s_norm, n_rec, n_final, _ = res
                soma_total_ano += n_final
                target.add_widget(OneLineListItem(
                    text=f"SOMA: {s_norm:.1f} | REC: {n_rec:.1f}",
                    theme_text_color="Hint"
                ))
                target.add_widget(OneLineListItem(
                    text=f"TOTAL TRIMESTRE: {n_final:.1f} pts",
                    theme_text_color="Custom",
                    text_color=(0.1, 0.5, 0.1, 1)
                ))

            # ⭐ CORREÇÃO: FREQUÊNCIA usando o método sincronizado
            freq_dados = db.obter_frequencia_aluno_consolidada(id_a, turma_id, i)
            
            # Atualiza totais anuais
            total_planejado_ano += freq_dados['total_planejado']
            total_presencas_ano += freq_dados['presencas']
            total_faltas_ano += freq_dados['faltas']
            
            if freq_dados['total_planejado'] > 0:
                # Define cor baseada no percentual
                perc = freq_dados['percentual']
                cor_freq = (0.2, 0.6, 0.2, 1) if perc >= 75 else \
                          (0.8, 0.5, 0, 1) if perc >= 60 else \
                          (0.8, 0.2, 0.2, 1)
                
                target.add_widget(OneLineListItem(
                    text=f"📊 FREQUÊNCIA: {perc:.1f}% ({freq_dados['presencas']} presenças / {freq_dados['faltas']} faltas / {freq_dados['total_planejado']} aulas)",
                    theme_text_color="Custom",
                    text_color=cor_freq
                ))

            # ⭐ LISTA DE AULAS (baseada no planejamento + status do aluno)
            aulas_detalhadas = db.obter_frequencia_detalhada_para_relatorio(id_a, turma_id, i)
            contador_aulas = 0
            
            for aula in aulas_detalhadas:
                data_aula = aula['data']
                tema = aula['tema']
                status = aula['status']
                justificativa = aula['justificativa']
                
                if status is None:
                    # Aula planejada mas sem chamada registrada
                    cor = (0.5, 0.5, 0.5, 1)
                    status_txt = '? NÃO REGISTRADA'
                    icone = '❓'
                elif status == 1:
                    cor = (0.2, 0.6, 0.2, 1)
                    status_txt = 'PRESENTE'
                    icone = '✅'
                else:  # status == 0
                    cor = (0.8, 0.2, 0.2, 1)
                    status_txt = 'FALTA'
                    icone = '❌'
                
                # Formatar data
                try:
                    data_obj = datetime.strptime(data_aula, "%Y-%m-%d")
                    data_exibicao = data_obj.strftime("%d/%m/%Y")
                except:
                    data_exibicao = data_aula
                
                texto_secundario = f"Data: {data_exibicao} - {icone} {status_txt}"
                if justificativa and justificativa not in ["None", ""]:
                    texto_secundario += f"\n📝 Justificativa: {justificativa[:50]}"
                
                target.add_widget(TwoLineListItem(
                    text=tema,
                    secondary_text=texto_secundario,
                    theme_text_color="Custom",
                    text_color=cor
                ))
                contador_aulas += 1
            
            print(f"   TRI {i}: {contador_aulas} aulas planejadas, {freq_dados['presencas']} presenças, {freq_dados['faltas']} faltas")

            # --- OCORRÊNCIAS ---
            todas_ocorrencias = db.buscar_ocorrencias(id_a) or []
            for reg in todas_ocorrencias:
                try:
                    if len(reg) >= 3:
                        d_h = str(reg[0])
                        msg = reg[1]
                        tri_oc = reg[2] if len(reg) > 2 else None
                        
                        if tri_oc == i:
                            data_ocorrencia = d_h[:10] if len(d_h) >= 10 else d_h
                            target.add_widget(TwoLineListItem(
                                text=f"📝 {data_ocorrencia}",
                                secondary_text=msg,
                                theme_text_color="Custom",
                                text_color=(0.1, 0.3, 0.6, 1)
                            ))
                except Exception as e:
                    print(f"   ⚠️ Erro ao processar ocorrência: {e}")

        # ⭐ Dashboard unificado (anual)
        if total_planejado_ano > 0:
            freq_anual = (total_presencas_ano / total_planejado_ano * 100)
            freq_anual = min(freq_anual, 100.0)
        else:
            freq_anual = 100.0
        
        self.ids.lbl_nota_total.text = f"{soma_total_ano:.1f} / 100.0"
        self.ids.lbl_frequencia.text = f"{freq_anual:.1f}%"
        self.ids.lbl_faltas.text = f"Total de Faltas: {total_faltas_ano}"
        
        print(f"✅ Relatório carregado - Total aulas planejadas ano: {total_planejado_ano}, Presenças: {total_presencas_ano}, Faltas: {total_faltas_ano}")

    def identificar_trimestre(self, data_txt, limites):
        """Função auxiliar para organizar datas nos trimestres"""
        if not data_txt:
            return 1

        if limites:
            for t_idx, (ini, fim) in limites.items():
                if ini <= data_txt <= fim:
                    return t_idx
        try:
            if '-' in data_txt:
                mes = int(data_txt.split("-")[1])
            else:
                mes = 1
            return 1 if mes <= 4 else 2 if mes <= 8 else 3
        except:
            return 1

    def forcar_recarga_completa(self, *args):
        """
        Botão de ATUALIZAR FORÇADO - Limpa tudo e recarrega do banco
        """
        print("\n" + "="*50)
        print("🔄 FORÇANDO RECARGA COMPLETA DO RELATÓRIO")
        print("="*50)

        app = MDApp.get_running_app()

        if not app.aluno_ativo_id:
            toast("Nenhum aluno selecionado!")
            return

        # 1. LIMPEZA RADICAL dos containers
        for i in range(1, 4):
            container_id = f"container_tri{i}"
            if container_id in self.ids:
                self.ids[container_id].clear_widgets()
                print(f"🗑️ Container TRI {i} esvaziado")

        # 2. Recarregar dados do banco
        self.carregar_dados_completos()

        toast("✅ Relatório atualizado com dados do banco!")
        print("✅ Recarga completa finalizada!")

    def atualizar_visualizacao_relatorio(self, *args):
        """Atualiza a tela de relatório - recarrega tudo"""
        self.forcar_recarga_completa()

    # ==================== MÉTODOS DE PDF ====================

    def acionar_geracao_pdf(self, *args):
        """Interface para escolha do trimestre para o PDF"""
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.list import MDList, OneLineListItem
        from kivy.uix.scrollview import ScrollView

        layout = MDBoxLayout(orientation="vertical", size_hint_y=None, height="220dp")
        scroll = ScrollView()
        lista = MDList()
        
        for i in range(1, 4):
            item = OneLineListItem(
                text=f"{i}º Trimestre",
                on_release=lambda x, t=i: self.confirmar_geracao_final(t)
            )
            lista.add_widget(item)
            
        scroll.add_widget(lista)
        layout.add_widget(scroll)
        
        self.dialogo_tri = MDDialog(
            title="Gerar PDF do Trimestre",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(
                    text="CANCELAR", 
                    on_release=lambda x: self.dialogo_tri.dismiss()
                )
            ]
        )
        self.dialogo_tri.open()

    def confirmar_geracao_final(self, tri_escolhido):
        """Gera o arquivo PDF final com os dados filtrados e tratados"""
        if self.dialogo_tri:
            self.dialogo_tri.dismiss()

        app = MDApp.get_running_app()
        db = app.db_manager
        id_a = app.aluno_ativo_id
        turma_id = getattr(app, 'turma_ativa_id', None)

        if not db or not id_a or not turma_id:
            toast("Erro: Dados do aluno ou turma ausentes")
            return

        try:
            # Coleta de dados do Professor e Turma
            prof_data = db.buscar_professor()
            if prof_data:
                prof_nome, prof_materia, prof_esfera, prof_inst, _ = prof_data
            else:
                prof_nome, prof_materia, prof_esfera, prof_inst = "-", "-", "-", "-"

            nome_turma = getattr(app, 'turma_ativa_nome', None)
            if not nome_turma:
                nome_turma = db.buscar_turma_nome(turma_id)
            nome_turma_final = str(nome_turma).upper() if nome_turma else "TURMA"

            # Notas e Recuperação
            notas_normais = db.buscar_notas_individuais_trimestre(id_a, tri_escolhido, "normal") or []
            recup_raw = db.buscar_notas_individuais_trimestre(id_a, tri_escolhido, "recuperacao")
            valor_recuperacao = float(recup_raw[0][1]) if recup_raw and len(recup_raw) > 0 and recup_raw[0][1] else 0.0

            # Frequência
            try:
                carga_tri = db.buscar_carga_planejada_trimestre(turma_id, tri_escolhido)
                faltas_tri, _, historico = db.buscar_frequencia_detalhada_tri(id_a, turma_id, tri_escolhido)
                faltas_ano, total_aulas_ano = db.calcular_frequencia_acumulada_anual(id_a, turma_id, tri_escolhido)

                if total_aulas_ano > 0:
                    p_aproveitamento_ano = min(100.0, ((total_aulas_ano - faltas_ano) / total_aulas_ano * 100))
                else:
                    p_aproveitamento_ano = 100.0
            except Exception as e:
                print(f"Erro no cálculo de frequência: {e}")
                carga_tri, faltas_tri, historico, faltas_ano, p_aproveitamento_ano = 0, 0, [], 0, 100.0

            # Caminho
            caminho_final = self.definir_caminho_pdf(tri_escolhido)
            if not caminho_final:
                toast("Erro: Caminho de salvamento inválido")
                return

            # Pacote de dados
            pacote_dados = {
                'aluno': str(getattr(app, 'aluno_ativo_nome', 'ESTUDANTE')).upper(),
                'professor': str(prof_nome).upper(),
                'escola': str(prof_inst).upper(),
                'fundacao': str(prof_esfera).upper(),
                'disciplina': str(getattr(app, 'disciplina_ativa_nome', prof_materia)).upper(),
                'turma': nome_turma_final,
                'trimestre': tri_escolhido,
                'ano': "2026",
                'data_emissao': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'caminho': caminho_final,
                'notas': notas_normais,
                'recuperacao': valor_recuperacao,
                'nota_anual': db.calcular_acumulado_ate_tri(id_a, turma_id, tri_escolhido) or 0,
                'frequencia': {
                    'aulas_tri': carga_tri or 0,
                    'faltas_tri': faltas_tri or 0,
                    'faltas_anual': faltas_ano or 0,
                    'perc_anual': f"{p_aproveitamento_ano:.1f}%"
                },
                'chamada': historico or [],
                'ocorrencias': db.buscar_ocorrencias(id_a) or []
            }

            # Geração do Arquivo
            from gerenciador_relatorio import GeradorRelatorio
            if GeradorRelatorio.criar_pdf(pacote_dados):
                toast("PDF gerado com sucesso!")
                if platform != 'android' and os.path.exists(caminho_final):
                    if os.name == 'nt':
                        os.startfile(caminho_final)
                    else:
                        os.system(f'open "{caminho_final}"')
            else:
                toast("Erro ao salvar arquivo PDF")

        except Exception as e:
            print(f"ERRO CRÍTICO NO PROCESSAMENTO: {e}")
            traceback.print_exc()
            toast("Houve um erro ao gerar o relatório")

    def definir_caminho_pdf(self, tri):
        """Define o caminho de salvamento baseado na plataforma"""
        app = MDApp.get_running_app()
        nome_a = str(app.aluno_ativo_nome).replace(' ', '_')
        turma_nome = str(getattr(app, 'turma_ativa_nome', 'Geral')).replace(' ', '_')

        if platform == 'android':
            base = "/storage/emulated/0/Documents/Gabaritus_backup/Relatorios"
        else:
            base = "Relatorios_Gerados"

        pasta_turma = os.path.join(base, turma_nome)
        if not os.path.exists(pasta_turma):
            os.makedirs(pasta_turma, exist_ok=True)

        return os.path.join(pasta_turma, f"Relatorio_T{tri}_{nome_a}.pdf")

# TELAS ADICIONAIS

class TelaConfiguracoes(Screen):
    pass

# --- APP PRINCIPAL ---
class GabaritusApp(MDApp):
    turma_ativa = StringProperty("Turma")
    aluno_ativo_id = ObjectProperty(None, allownone=True)
    aluno_ativo_nome = StringProperty("Aluno")
    atividade_ativa_id = ObjectProperty(None, allownone=True)
    atividade_ativa_nome = StringProperty("Atividade")  # ✅ CORRIGIDO
    atividade_ativa_turma = StringProperty("")
    gabaritos_versoes = ObjectProperty({'A': [], 'B': [], 'C': [], 'D': []})
    
    # Variáveis de controle de fluxo
    trimestre_global = StringProperty("1")
    data_temporaria_planejamento = StringProperty("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 📂 Variáveis globais do Gerenciador de Arquivos Único
        self.file_manager = None
        self.file_mode = None  # Armazena: "CSV", "PLAN_EXEC" ou "NOTAS_EXEC"
        self.caminho_planilha = None
        self.gerenciador_planilha = None
    
    def gerar_botoes_trimestre(self, objeto_tela, callback_funcao):
        """Gera os botões de TRI e mapeia no dicionário da tela"""
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDRaisedButton
        
        layout_tri = MDBoxLayout(adaptive_height=True, spacing="8dp", padding=[0, 0, 0, 10])
        objeto_tela.botoes_tri = {}
        
        tri_atual = str(self.trimestre_global)

        for tri in ["1", "2", "3"]:
            cor = (0.33, 0.42, 0.18, 1) if tri == tri_atual else (0.5, 0.5, 0.5, 1)
            
            btn = MDRaisedButton(
                text=f"{tri}º TRI",
                md_bg_color=cor,
                on_release=lambda x, t=tri: callback_funcao(t)
            )
            layout_tri.add_widget(btn)
            objeto_tela.botoes_tri[tri] = btn
            
        return layout_tri

    def ir_para_planejamento(self, data_foco):
        """Lógica de Desvio para a tela de planejamento"""
        self.data_temporaria_planejamento = data_foco
        if self.root.ids.screen_manager:
            self.root.ids.screen_manager.current = "tela_planejamento"
            toast(f"Defina a aula para {data_foco}")

    # ==================== MOTOR DE ARQUIVOS GLOBAL ====================
    def abrir_seletor_global(self, modo, extensoes):
        """
        Abre o gerenciador de arquivos em qualquer tela do app.
        modo: "CSV", "PLAN_EXEC" ou "NOTAS_EXEC"
        extensoes: ['.csv'] ou ['.xlsx']
        """
        import os
        from kivy.utils import platform as kivy_platform

        self.file_mode = modo
        
        # 🤖 CONFIGURAÇÃO DE CAMINHO FOCADO EM DOWNLOADS
        if kivy_platform == 'android':
            # No Android, a pasta padrão pública é no singular: "Download"
            caminho_inicial = "/storage/emulated/0/"
            
            # Garantia: tenta criar se por algum motivo bizarro não existir
            try:
                if not os.path.exists(caminho_inicial):
                    os.makedirs(caminho_inicial)
            except Exception:
                # Fallback de segurança caso dê erro de permissão na pasta Download
                caminho_inicial = "/storage/emulated/0/"
        else:
            # Caminho de testes para o Computador (Windows/Linux/Mac)
            # No PC, a pasta padrão costuma ser no plural: "Downloads"
            caminho_inicial = os.path.join(os.path.expanduser("~"), "Downloads")
            
            if not os.path.exists(caminho_inicial):
                # Fallback secundário para sistemas que usam no singular "Download"
                caminho_inicial = os.path.join(os.path.expanduser("~"), "Download")
                if not os.path.exists(caminho_inicial):
                    caminho_inicial = os.path.expanduser("~")

        # Garante o encerramento seguro de instâncias fantasmas
        self.fechar_seletor_global()

        # Configura o gerenciador puro do KivyMD
        from kivymd.uix.filemanager import MDFileManager
        self.file_manager = MDFileManager(
            exit_manager=self.fechar_seletor_global,
            select_path=self.retorno_seletor_global,
            preview=False,
            ext=extensoes
        )
        
        # Abre o gerenciador apontando para a pasta definida
        self.file_manager.show(caminho_inicial)
   
    def fechar_seletor_global(self, *args):
        """Fecha o gerenciador global com segurança"""
        if hasattr(self, 'file_manager') and self.file_manager:
            self.file_manager.close()
            self.file_manager = None

    def retorno_seletor_global(self, path):
        """
        Fecha o diálogo do seletor e entrega o caminho do arquivo 
        direto na mão da tela responsável por processá-lo.
        """
        from kivymd.toast import toast
        import os

        # 1. Fecha o diálogo do seletor (se existir)
        if hasattr(self, 'dialogo_seletor') and self.dialogo_seletor:
            try:
                self.dialogo_seletor.dismiss()
            except Exception as e:
                print(f"⚠️ Erro ao fechar dialogo_seletor: {e}")
            self.dialogo_seletor = None
            
        # 2. Fecha o file_manager também
        if hasattr(self, 'file_manager') and self.file_manager:
            try:
                self.file_manager.close()
            except Exception:
                pass
            self.file_manager = None
            
        # 3. Localiza a tela ativa
        try:
            if not self.root:
                print("❌ self.root é None!")
                toast("Erro: aplicação não inicializada")
                return
                
            # Tenta diferentes formas de acessar o ScreenManager
            sm = self._obter_screen_manager()
            
            if not sm:
                print("❌ Nenhum ScreenManager encontrado!")
                toast("Erro: gerenciador de telas não encontrado")
                return
            
            print(f"🔄 Modo de arquivo: {self.file_mode}")
            print(f"📁 Path recebido: {path}")

            # 4. Encaminha o arquivo baseado no modo
            if self.file_mode == "NOTAS_EXEC":
                self._processar_notas_exec(sm, path)
            elif self.file_mode == "PLAN_EXEC":
                self._processar_plan_exec(sm, path)
            elif self.file_mode == "CHAMADA_EXEC":
                self._processar_chamada_exec(sm, path)
            elif self.file_mode == "CSV":
                self._processar_csv(sm, path)
            else:
                print(f"⚠️ Modo não reconhecido: '{self.file_mode}'")
                toast(f"Modo não suportado: {self.file_mode}")
                    
        except Exception as e:
            print(f"❌ Erro no retorno do seletor: {e}")
            import traceback
            traceback.print_exc()
            toast("Erro ao processar arquivo")

    def _obter_screen_manager(self):
        """Obtém o ScreenManager de forma robusta"""
        if not self.root:
            return None
        
        # Tenta diferentes formas
        if hasattr(self.root, 'ids'):
            if hasattr(self.root.ids, 'screen_manager'):
                return self.root.ids.screen_manager
            if hasattr(self.root.ids, 'sm'):
                return self.root.ids.sm
        
        if hasattr(self.root, 'manager'):
            return self.root.manager
        
        # Busca recursiva
        from kivy.uix.screenmanager import ScreenManager
        def buscar(widget):
            if isinstance(widget, ScreenManager):
                return widget
            for child in widget.children:
                resultado = buscar(child)
                if resultado:
                    return resultado
            return None
        
        return buscar(self.root)

    def _processar_csv(self, sm, path):
        """Processa arquivo CSV (importação de alunos)"""
        from kivymd.toast import toast
        
        print("📄 Processando modo CSV...")
        tela_csv = None
        
        # Se a sua classe principal tiver a função direta '_obter_tela_chamada'
        if hasattr(self, '_obter_tela_chamada'):
            tela_chamada = self._obter_tela_chamada(sm)
            if tela_chamada and hasattr(tela_chamada, 'importar_csv'):
                tela_csv = tela_chamada
                print("✅ Usando tela_chamada.importar_csv()")
        
        # Fallback: se não achou pela função, varre as telas do ScreenManager
        if not tela_csv:
            for screen_name in sm.screen_names:
                try:
                    tela = sm.get_screen(screen_name)
                    if hasattr(tela, 'importar_csv'):
                        tela_csv = tela
                        print(f"✅ Encontrado importar_csv na tela: {screen_name}")
                        break
                except Exception:
                    continue
        
        if tela_csv:
            try:
                tela_csv.importar_csv(path)
                print("✅ CSV processado com sucesso!")
            except Exception as e:
                print(f"❌ Erro ao processar CSV: {e}")
                toast(f"Erro ao importar: {str(e)[:40]}")
        else:
            print("❌ Nenhuma tela com método 'importar_csv' encontrada!")
            print(f"📋 Telas disponíveis: {sm.screen_names}")
            toast("Função de importação CSV não disponível nesta tela")

    def _processar_notas_exec(self, sm, path):
        """Processa arquivo de notas (Excel)"""
        from kivymd.toast import toast
        
        tela_gabarito = None
        for nome in ['gabarito_screen', 'TelaGabarito']:
            try:
                if sm.has_screen(nome):
                    tela_gabarito = sm.get_screen(nome)
                    print(f"✅ Tela encontrada: {nome}")
                    break
            except Exception:
                continue
        
        if tela_gabarito and hasattr(tela_gabarito, 'abrir_seletor_atividades'):
            tela_gabarito.abrir_seletor_atividades(path)
        else:
            print("❌ Método 'abrir_seletor_atividades' não encontrado!")
            toast("Função de notas não disponível")

    def _processar_plan_exec(self, sm, path):
        """Processa planilha de planejamento"""
        from kivymd.toast import toast
        
        tela_chamada = self._obter_tela_chamada(sm)
        if tela_chamada and hasattr(tela_chamada, 'processar_planilha_planejamento'):
            tela_chamada.processar_planilha_planejamento(path)
        else:
            print("❌ Método 'processar_planilha_planejamento' não encontrado!")
            toast("Função de planejamento não disponível")

    def _processar_chamada_exec(self, sm, path):
        """Processa planilha de chamada"""
        from kivymd.toast import toast
        
        tela_chamada = self._obter_tela_chamada(sm)
        if tela_chamada and hasattr(tela_chamada, 'processar_planilha_chamada'):
            tela_chamada.processar_planilha_chamada(path)
        else:
            print("❌ Método 'processar_planilha_chamada' não encontrado!")
            toast("Função de chamada não disponível")

    def _obter_tela_chamada(self, sm):
        """Obtém a tela de chamada atual de forma mais precisa"""
        from kivymd.toast import toast
        
        # Tenta pelo nome atual do ScreenManager
        if hasattr(sm, 'current'):
            try:
                tela_atual = sm.get_screen(sm.current)
                # Verifica se a tela atual tem métodos de chamada
                metodos_esperados = ['importar_csv', 'processar_planilha_chamada', 'processar_planilha_planejamento']
                if any(hasattr(tela_atual, m) for m in metodos_esperados):
                    print(f"✅ Usando tela atual: {sm.current}")
                    return tela_atual
            except Exception:
                pass
        
        # Lista de nomes possíveis em ordem de prioridade
        nomes_possiveis = ['chamada_screen', 'tela_chamada', 'chamada', 'home', 'principal']
        
        for nome in nomes_possiveis:
            try:
                if sm.has_screen(nome):
                    print(f"✅ Tela de chamada encontrada pelo nome: {nome}")
                    return sm.get_screen(nome)
            except Exception:
                continue
        
        # Fallback: primeira tela que tiver métodos de chamada
        for screen_name in sm.screen_names:
            try:
                tela = sm.get_screen(screen_name)
                if hasattr(tela, 'importar_csv') or hasattr(tela, 'processar_planilha_chamada'):
                    print(f"✅ Tela com métodos de chamada encontrada: {screen_name}")
                    return tela
            except Exception:
                continue
        
        print("⚠️ Nenhuma tela de chamada encontrada")
        return None


    def build(self):
        self.theme_cls.primary_palette = "Green"
        self.db_manager = Database()
        self.trimestre_global = "1"
        return Builder.load_string(KV)

# --- INTERFACE KV ---

KV = """
<ItemCheckDiario>:
    adaptive_height: True
    padding: "10dp"
    MDCheckbox:
        id: cb
        size_hint: None, None
        size: "48dp", "48dp"
        pos_hint: {'center_y':.5}
        on_active: root.atualizar_selecao(root.text, self.active)
    MDLabel:
        text: root.text
        theme_text_color: "Secondary"
        pos_hint: {'center_y':.5}

<ConteudoCategoria>:
    orientation: 'vertical'
    adaptive_height: True
    MDBoxLayout:
        id: container_itens
        orientation: 'vertical'
        adaptive_height: True

<ConteudoDialogoChamada>:
    orientation: "vertical"
    spacing: "12dp"
    padding: "16dp"
    size_hint_y: None
    adaptive_height: True  # Alterado de height fixo para evitar erros de renderização

    MDTextField:
        id: tema_aula
        hint_text: "Tema/Conteúdo da Aula"
        mode: "rectangle"
        # Garante que o foco use a cor do seu projeto (Verde Oliva)
        line_color_focus: 0.33, 0.42, 0.18, 1 

    MDRaisedButton:
        text: "ALTERAR DATA DA AULA"
        pos_hint: {"center_x": .5}
        md_bg_color: 0.33, 0.42, 0.18, 1
        on_release: root.abrir_calendario()

    MDLabel:
        id: data_selecionada
        text: "Data: Hoje (Padrão)"
        halign: "center"
        theme_text_color: "Secondary"
        font_style: "Caption"

<ConteudoSelecaoAlunoDiario>:
    orientation: "vertical"
    spacing: "12dp"
    size_hint_y: None
    height: "400dp"
    ScrollView:
        MDList:
            id: lista_selecao_alunos

<ConteudoGabaritoMestre>:
    orientation: "vertical"
    spacing: "10dp"
    padding: "10dp"
    adaptive_height: True
    MDBoxLayout:
        adaptive_height: True
        spacing: "10dp"
        MDTextField:
            id: qtd_questoes
            hint_text: "Qtd"
            text: "10"
            input_filter: "int"
            mode: "rectangle"
            size_hint_x: 0.3
        MDTextField:
            id: campo_mestre
            hint_text: "Respostas Mestre (Ex: ABCDE...)"
            mode: "rectangle"
            size_hint_x: 0.7
            on_text: root.validar_texto(self)
    MDRaisedButton:
        text: "GERAR E CONFERIR VERSÕES"
        md_bg_color: 0.33, 0.42, 0.18, 1
        size_hint_x: 1
        on_release: root.gerar_e_exibir()
    ScrollView:
        size_hint_y: None
        height: "120dp"
        MDLabel:
            id: area_conferencia
            text: "Versões A, B, C e D aparecerão aqui..."
            font_style: "Caption"
            theme_text_color: "Secondary"
    MDRaisedButton:
        id: btn_gerar_pdf
        text: "2. GERAR PDF COM QR CODE"
        icon: "file-pdf-box"
        md_bg_color: 0.2, 0.3, 0.1, 1
        size_hint_x: 1
        disabled: True
        on_release: root.acao_gerar_pdf()

ScreenManager:
    TelaLogin:
    TelaCadastro:
    TelaDisciplinas:
    TelaTurmas:
    TelaDiario:
    TelaChamada:
    TelaGabarito:
    TelaLancamentoNotas:
    TelaRelatorio:
    
        
<TelaLogin>:
    name: "login_screen"
    MDBoxLayout:
        orientation: "vertical"

        # TOPO - Logo
        AnchorLayout:
            anchor_y: "top"
            size_hint_y: None
            height: "200dp"
            padding: "20dp", "40dp", "20dp", "0dp"
            Image:
                source: "logo.png"
                size_hint_y: None
                height: "450dp"
                allow_stretch: True
                keep_ratio: True

        # MEIO - Campos (centralizado)
        AnchorLayout:
            anchor_y: "center"
            MDBoxLayout:
                orientation: "vertical"
                spacing: "20dp"
                padding: "20dp"
                size_hint: .9, None
                height: self.minimum_height

                MDTextField:
                    id: senha_login
                    hint_text: "Senha de Acesso"
                    password: True
                    mode: "fill"
                    size_hint_x: 1
                    fill_color: 1, 1, 1, 1

                MDRaisedButton:
                    text: "ENTRAR"
                    size_hint_x: 1
                    md_bg_color: 0.33, 0.42, 0.18, 1
                    on_release: root.fazer_login()

                MDTextButton:
                    text: "Esqueci minha senha"
                    pos_hint: {"center_x": 0.5}
                    theme_text_color: "Custom"
                    text_color: 0.33, 0.42, 0.18, 1
                    on_release: root.recuperar_senha()

        # RODAPÉ - Créditos
        AnchorLayout:
            anchor_y: "bottom"
            size_hint_y: None
            height: "40dp"
            MDLabel:
                text: "@2026 by Jocélio Grangeiro Vieira"
                halign: "center"
                font_style: "Caption"
                theme_text_color: "Secondary"

<TelaCadastro>:
    name: "cadastro_prof_screen"
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: "Cadastro do Professor"
            md_bg_color: 0.33, 0.42, 0.18, 1
        ScrollView:
            MDBoxLayout:
                orientation: 'vertical'
                padding: "20dp"
                spacing: "15dp"
                adaptive_height: True
                MDTextField:
                    id: nome_prof
                    hint_text: "Nome Completo"
                    mode: "rectangle"
                MDTextField:
                    id: esfera_prof
                    hint_text: "Esfera (Ex: Municipal)"
                    mode: "rectangle"
                MDTextField:
                    id: inst_prof
                    hint_text: "Instituição (Escola)"
                    mode: "rectangle"
                MDTextField:
                    id: sec_prof
                    hint_text: "Secretaria / Órgão"
                    text: "Secretaria Municipal de Educação de Contagem"
                    mode: "rectangle"
                MDRaisedButton:
                    text: "SALVAR E CONTINUAR"
                    size_hint_x: 1
                    md_bg_color: 0.33, 0.42, 0.18, 1
                    on_release: root.salvar_perfil()

<TelaDisciplinas>:
    name: "disciplinas_screen"
    MDBoxLayout:
        orientation: 'vertical'
        
        MDTopAppBar:
            title: "Minhas Disciplinas"
            md_bg_color: 0.33, 0.42, 0.18, 1
            left_action_items: [["logout", lambda x: root.fazer_logout()]]
            right_action_items: 
                [
                ["calendar-clock", lambda x: root.abrir_configuracao_trimestres()], 
                ["plus", lambda x: root.mostrar_input_disciplina()]
                ]

        
        MDBoxLayout:
            orientation: 'vertical'
            padding: "10dp"
            spacing: "5dp"
            
            MDLabel:
                text: "Selecione a matéria para gerenciar as turmas:"
                font_style: "Caption"
                theme_text_color: "Secondary"
                adaptive_height: True
                padding_x: "15dp"

            ScrollView:
                MDList:
                    id: container_disciplinas
                    spacing: "8dp"
                    padding: "8dp"

        # Rodapé com identificação (opcional, para manter o estilo da Login)
        MDLabel:
            text: "Gabaritus - Gestão por Disciplina"
            halign: "center"
            font_style: "Caption"
            theme_text_color: "Hint"
            adaptive_height: True
            padding: "5dp"

<TelaTurmas>:
    name: "turmas_screen"
    
    MDBoxLayout:
        orientation: 'vertical'
        
        MDTopAppBar:
            title: "Minhas Turmas"
            md_bg_color: 0.33, 0.42, 0.18, 1
            left_action_items: [["arrow-left", lambda x: root.voltar()]]
            right_action_items: [["plus", lambda x: root.mostrar_input_turma()]]

        MDLabel:
            id: label_materia
            text: "Carregando matéria..."
            halign: "center"
            bold: True
            size_hint_y: None
            height: "50dp"

        ScrollView:
            MDList:
                id: container_turmas
<AdminContent@MDBoxLayout>:
    orientation: 'vertical'
    adaptive_height: True
    id: container_itens_admin

<PedagContent@MDBoxLayout>:
    orientation: 'vertical'
    adaptive_height: True
    id: container_itens_pedag

<CompContent@MDBoxLayout>:
    orientation: 'vertical'
    adaptive_height: True
    id: container_itens_comp

<TelaDiario>:
    name: "diario_screen"
    md_bg_color: 0.95, 0.95, 0.95, 1

    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            id: toolbar_diario
            title: "Diário de Ocorrências"
            md_bg_color: 0.33, 0.42, 0.18, 1
            elevation: 4
            # Mudamos para chamar a lógica de salvar/voltar que prepara o relatório
            left_action_items: [["arrow-left", lambda x: root.salvar_diario()]]

        ScrollView:
            do_scroll_x: False
            MDBoxLayout:
                orientation: 'vertical'
                adaptive_height: True
                padding: "12dp"
                spacing: "15dp"

                # --- CATEGORIA: ADMINISTRATIVO ---
                MDCard:
                    orientation: 'vertical'
                    adaptive_height: True
                    radius: [15,]
                    elevation: 1
                    
                    MDBoxLayout:
                        size_hint_y: None
                        height: "50dp"
                        padding: ["10dp", 0]
                        md_bg_color: 0.9, 0.9, 0.8, 1
                        
                        MDLabel:
                            text: "📋 ADMINISTRATIVO"
                            bold: True
                        MDIconButton:
                            icon: "plus-circle-outline"
                            on_release: root.abrir_dialogo_novo("admin")
                        MDIconButton:
                            icon: "chevron-down"
                            on_release: root.alternar_painel("admin")

                    MDGridLayout:
                        id: container_admin
                        cols: 1
                        adaptive_height: True
                        padding: "10dp"
                        spacing: "5dp"
                        # Essencial para o efeito de abrir/fechar:
                        height: 0
                        opacity: 0
                        disabled: True
                
                # --- CATEGORIA: PEDAGÓGICO ---
                MDCard:
                    orientation: 'vertical'
                    adaptive_height: True
                    radius: [15,]
                    elevation: 1
                    
                    MDBoxLayout:
                        size_hint_y: None
                        height: "50dp"
                        padding: ["10dp", 0]
                        md_bg_color: 0.8, 0.9, 0.9, 1
                        
                        MDLabel:
                            text: "📚 PEDAGÓGICO"
                            bold: True
                        MDIconButton:
                            icon: "plus-circle-outline"
                            on_release: root.abrir_dialogo_novo("pedag")
                        MDIconButton:
                            icon: "chevron-down"
                            on_release: root.alternar_painel("pedag")

                    MDGridLayout:
                        id: container_pedag
                        cols: 1
                        adaptive_height: True
                        padding: "10dp"
                        spacing: "5dp"
                        height: 0
                        opacity: 0
                        disabled: True

                # --- CATEGORIA: COMPORTAMENTAL ---
                MDCard:
                    orientation: 'vertical'
                    adaptive_height: True
                    radius: [15,]
                    elevation: 1
                    
                    MDBoxLayout:
                        size_hint_y: None
                        height: "50dp"
                        padding: ["10dp", 0]
                        md_bg_color: 0.9, 0.8, 0.9, 1
                        
                        MDLabel:
                            text: "😊 COMPORTAMENTAL"
                            bold: True
                        MDIconButton:
                            icon: "plus-circle-outline"
                            on_release: root.abrir_dialogo_novo("comp")
                        MDIconButton:
                            icon: "chevron-down"
                            on_release: root.alternar_painel("comp")

                    MDGridLayout:
                        id: container_comp
                        cols: 1
                        adaptive_height: True
                        padding: "10dp"
                        spacing: "5dp"
                        height: 0
                        opacity: 0
                        disabled: True

                # --- CAMPO DE OBSERVAÇÕES ---
                MDTextField:
                    id: campo_obs
                    hint_text: "Observações adicionais (opcional)"
                    mode: "rectangle"
                    multiline: True
                    size_hint_y: None
                    height: "100dp"

        # RODAPÉ FIXO
        MDBoxLayout:
            size_hint_y: None
            height: "70dp"
            padding: "10dp"
            spacing: "10dp"
            md_bg_color: 1, 1, 1, 1

            MDRaisedButton:
                text: "CANCELAR"
                size_hint_x: 0.5
                md_bg_color: 0.8, 0.8, 0.8, 1
                text_color: 0, 0, 0, 1
                on_release: root.manager.current = "chamada_screen"

            MDRaisedButton:
                text: "SALVAR"
                size_hint_x: 0.5
                md_bg_color: 0.33, 0.42, 0.18, 1
                on_release: root.salvar_diario()
                
<TelaChamada>:
    name: "chamada_screen"
    md_bg_color: app.theme_cls.bg_normal
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: "Chamada: " + app.turma_ativa
            md_bg_color: 0.33, 0.42, 0.18, 1
            left_action_items: [["arrow-left", lambda x: setattr(app.root, 'current', 'turmas_screen')]]

            right_action_items:
                [
                # 📊 SINCRONIZAR CHAMADA/DIÁRIO (Excel .xlsx)
                ["notebook-edit", lambda x: root.abrir_popup_selecao_diario()],
                
                ["clipboard-edit-outline", lambda x: setattr(app.root, 'current', 'gabarito_screen')],
                
                # 📅 SINCRONIZAR CRONOGRAMA/PLANEJAMENTO (Excel .xlsx)
                ["calendar-text", lambda x: root.abrir_planejamento()],
                
                # 📥 IMPORTAR ALUNOS (CSV .csv)
                ["file-upload", lambda x: app.abrir_seletor_global("CSV", ['.csv'])],
                
                ["account-plus", lambda x: root.abrir_dialogo_aluno()]
                ]

        ScrollView:
            MDList:
                id: lista_alunos_chamada
        MDRaisedButton:
            text: "REGISTRO DE CHAMADA"
            size_hint_x: 1
            md_bg_color: 0.33, 0.42, 0.18, 1
            on_release: root.abrir_popup_registro_aula()

<TelaGabarito>:
    name: "gabarito_screen"
    
    MDFloatLayout:
        MDBoxLayout:
            orientation: 'vertical'
            pos_hint: {"top": 1}
            
            MDTopAppBar:
                title: "Atividades: " + app.turma_ativa
                md_bg_color: 0.33, 0.42, 0.18, 1
                left_action_items: [["arrow-left", lambda x: setattr(app.root, 'current', 'chamada_screen')]]
                right_action_items: 
                    [
                    ["sync", lambda x: app.abrir_seletor_global("NOTAS_EXEC", ['.xlsx'])],
                    ["delete-outline", lambda x: root.abrir_dialogo_excluir()], 
                    ["plus", lambda x: root.abrir_dialogo_nova_atividade()]
                    ]
                    
            ScrollView:
                MDList:
                    id: lista_atividades

<TelaLancamentoNotas>:
    name: "lancamento_screen"
    MDBoxLayout:
        orientation: 'vertical'
        MDTopAppBar:
            title: "Notas: " + app.atividade_ativa_nome
            md_bg_color: 0.33, 0.42, 0.18, 1
            left_action_items: [["arrow-left", lambda x: setattr(app.root, 'current', 'gabarito_screen')]]
        ScrollView:
            MDList:
                id: container_alunos_notas
        MDRaisedButton:
            text: "SALVAR NOTAS"
            md_bg_color: 0.33, 0.42, 0.18, 1
            size_hint_x: 1
            on_release: root.salvar_notas_lote()

<TelaRelatorio>:
    name: "relatorio_screen"
    MDBoxLayout:
        orientation: 'vertical'
        md_bg_color: 0.98, 0.98, 0.98, 1

               # --- TOOLBAR FIXA ---
        MDTopAppBar:
            id: toolbar_relatorio
            title: "Relatório de Desempenho"
            elevation: 4
            md_bg_color: 0.33, 0.42, 0.18, 1
            # O segredo está aqui: root.manager.current
            left_action_items: [["arrow-left", lambda x: setattr(root.manager, 'current', 'chamada_screen')]]


        # --- DASHBOARD FIXO (AUMENTADO PARA NÃO ENCAVALAR) ---
        MDBoxLayout:
            orientation: 'vertical'
            adaptive_height: True
            padding: ["12dp", "16dp", "12dp", "12dp"]
            spacing: "12dp"
            md_bg_color: 1, 1, 1, 1

            MDLabel:
                id: lbl_nome_aluno_topo
                text: "NOME DO ESTUDANTE"
                font_style: "H6"
                bold: True
                halign: "center"
                theme_text_color: "Custom"
                text_color: 0.33, 0.42, 0.18, 1

            MDGridLayout:
                cols: 2
                adaptive_height: True
                spacing: "12dp"

                # Card de Notas Acumuladas
                MDCard:
                    orientation: 'vertical'
                    padding: "10dp"
                    size_hint_y: None
                    height: "100dp" # Altura maior para evitar sobreposição
                    elevation: 1
                    radius: [12,]
                    MDLabel:
                        text: "Nota Total (Ano)"
                        font_style: "Caption"
                        halign: "center"
                    MDLabel:
                        id: lbl_nota_total
                        text: "0.0 / 60.0"
                        font_style: "H5"
                        bold: True
                        halign: "center"

                                # Card de Frequência
                MDCard:
                    orientation: 'vertical'
                    padding: "10dp"
                    size_hint_y: None
                    height: "100dp"
                    elevation: 1
                    radius: [12,]
                    MDLabel:
                        id: lbl_faltas
                        text: "Frequência Geral"
                        font_style: "Caption"
                        halign: "center"
                    MDLabel:
                        id: lbl_frequencia
                        text: "100%"
                        font_style: "H5"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.1, 0.4, 0.1, 1

        MDSeparator: # Linha sutil para separar o topo da lista
            height: "1dp"

        # --- ÁREA DE ROLAGEM COM OS TRIMESTRES ---
        ScrollView:
            do_scroll_x: False
            MDBoxLayout:
                orientation: 'vertical'
                adaptive_height: True
                padding: "12dp"
                spacing: "16dp"

                # --- 1º TRIMESTRE ---
                MDCard:
                    orientation: 'vertical'
                    adaptive_height: True
                    elevation: 1
                    radius: [12,]
                    
                    MDRectangleFlatIconButton:
                        text: "1º TRIMESTRE - DETALHES"
                        icon: "chevron-down"
                        size_hint_x: 1
                        height: "50dp"
                        line_color: 0, 0, 0, 0 # Remove a linha chata do botão
                        on_release: root.alternar_painel("tri1")
                    
                    MDBoxLayout:
                        id: container_tri1
                        orientation: 'vertical'
                        adaptive_height: True
                        opacity: 0
                        height: 0
                        disabled: True
                        padding: ["12dp", "0dp", "12dp", "12dp"]
                        spacing: "8dp"

                # --- 2º TRIMESTRE ---
                MDCard:
                    orientation: 'vertical'
                    adaptive_height: True
                    elevation: 1
                    radius: [12,]
                    
                    MDRectangleFlatIconButton:
                        text: "2º TRIMESTRE - DETALHES"
                        icon: "chevron-down"
                        size_hint_x: 1
                        height: "50dp"
                        line_color: 0, 0, 0, 0
                        on_release: root.alternar_painel("tri2")
                    
                    MDBoxLayout:
                        id: container_tri2
                        orientation: 'vertical'
                        adaptive_height: True
                        opacity: 0
                        height: 0
                        disabled: True
                        padding: ["12dp", "0dp", "12dp", "12dp"]
                        spacing: "8dp"

                # --- 3º TRIMESTRE ---
                MDCard:
                    orientation: 'vertical'
                    adaptive_height: True
                    elevation: 1
                    radius: [12,]
                    
                    MDRectangleFlatIconButton:
                        text: "3º TRIMESTRE - DETALHES"
                        icon: "chevron-down"
                        size_hint_x: 1
                        height: "50dp"
                        line_color: 0, 0, 0, 0
                        on_release: root.alternar_painel("tri3")
                    
                    MDBoxLayout:
                        id: container_tri3
                        orientation: 'vertical'
                        adaptive_height: True
                        opacity: 0
                        height: 0
                        disabled: True
                        padding: ["12dp", "0dp", "12dp", "12dp"]
                        spacing: "8dp"

        # --- BOTÕES DE AÇÃO (RODAPÉ FIXO) ---
        MDBoxLayout:
            adaptive_height: True
            padding: "12dp"
            spacing: "15dp"
            md_bg_color: 1, 1, 1, 1 # Fundo branco para destacar os botões
            

                  # --- BOTÕES DE AÇÃO (RODAPÉ FIXO) ---
        MDBoxLayout:
            adaptive_height: True
            padding: "12dp"
            spacing: "15dp"
            md_bg_color: 1, 1, 1, 1 # Fundo branco para destacar os botões

            MDFillRoundFlatIconButton:
                icon: "refresh"
                text: "ATUALIZAR"
                size_hint_x: 1
                md_bg_color: 0.2, 0.4, 0.2, 1 
                on_release: root.forcar_recarga_completa()

            MDFillRoundFlatIconButton:
                icon: "file-pdf-box"
                text: "GERAR PDF"
                size_hint_x: 1
                md_bg_color: 0.5, 0.1, 0.1, 1
                on_release: root.acionar_geracao_pdf()
"""
if __name__ == "__main__":
    GabaritusApp().run()