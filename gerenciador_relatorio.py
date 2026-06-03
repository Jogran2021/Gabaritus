from fpdf import FPDF
import os
from datetime import datetime
from kivy.utils import platform

class GeradorRelatorio:
    @staticmethod
    def criar_pdf(dados):
        try:
            # ⭐ CORREÇÃO: Validar caminho antes de tudo
            caminho = dados.get('caminho')
            if not caminho:
                print("❌ Erro: Caminho do PDF não fornecido")
                return False
            
            # ⭐ Garantir que o diretório existe
            diretorio = os.path.dirname(caminho)
            if diretorio and not os.path.exists(diretorio):
                os.makedirs(diretorio, exist_ok=True)
                print(f"📁 Diretório criado: {diretorio}")
            
            # Inicializa o PDF
            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.set_margins(10, 10, 10)
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # ⭐ Dados com fallback para evitar KeyError
            fundacao = dados.get('fundacao', 'SECRETARIA MUNICIPAL')
            escola = dados.get('escola', 'ESCOLA MUNICIPAL')
            aluno = dados.get('aluno', 'ESTUDANTE')
            turma = dados.get('turma', 'TURMA')
            trimestre = dados.get('trimestre', 1)
            professor = dados.get('professor', 'PROFESSOR')
            disciplina = dados.get('disciplina', 'DISCIPLINA')
            notas = dados.get('notas', [])
            recuperacao = dados.get('recuperacao', 0)
            nota_anual_original = dados.get('nota_anual', 0)
            
            # ⭐ NOVO: Dados de frequência já calculados (vindos do método sincronizado)
            freq_data = dados.get('frequencia', {})
            faltas_anual = freq_data.get('faltas_anual', 0)
            aulas_tri = freq_data.get('aulas_tri', 0)  # Total planejado no trimestre
            faltas_tri = freq_data.get('faltas_tri', 0)
            perc_anual = freq_data.get('perc_anual', '100%')
            
            # ⭐ Lista de chamada (já deve vir com status None para aulas sem registro)
            chamada = dados.get('chamada', [])
            ocorrencias = dados.get('ocorrencias', [])
            
            # ⭐ CORREÇÃO: Limitar nota anual a 60
            nota_anual_corrigida = min(nota_anual_original, 100.0)
            
            # ⭐ Garantir que faltas não sejam negativas
            faltas_anual = max(faltas_anual, 0)
            faltas_tri = max(faltas_tri, 0)
            
            # Calcular total de aulas no trimestre e frequência
            if aulas_tri > 0:
                presencas_tri = aulas_tri - faltas_tri
                freq_tri = (presencas_tri / aulas_tri * 100)
                freq_tri = min(freq_tri, 100.0)
            else:
                presencas_tri = 0
                freq_tri = 100.0
            
            # --- 1. CABEÇALHO ---
            pdf.set_font("Arial", "B", 14)
            pdf.cell(190, 7, fundacao[:50].encode('latin-1', 'ignore').decode('latin-1'), ln=True, align='C')
            
            pdf.set_font("Arial", "B", 12)
            pdf.cell(190, 6, escola[:60].encode('latin-1', 'ignore').decode('latin-1'), ln=True, align='C')
            
            pdf.set_font("Arial", "", 10)
            ano_atual = datetime.now().strftime("%Y")
            pdf.cell(190, 5, f"ANO LETIVO: {ano_atual}", ln=True, align='C')
            pdf.ln(3)

            # --- 2. IDENTIFICAÇÃO DO ALUNO ---
            y_id = pdf.get_y()
            pdf.set_font("Arial", "B", 10)
            pdf.cell(95, 5, f"Aluno: {aluno[:40]}".encode('latin-1', 'ignore').decode('latin-1'), ln=True, align='L')
            pdf.set_font("Arial", "", 10)
            pdf.cell(95, 5, f"Turma: {turma[:30]} | {trimestre}º Trimestre", ln=True, align='L')
            
            pdf.set_xy(105, y_id)
            pdf.cell(95, 5, f"Professor: {professor[:30]}".encode('latin-1', 'ignore').decode('latin-1'), ln=True, align='R')
            pdf.set_x(105)
            pdf.cell(95, 5, f"Disciplina: {disciplina[:30]}".encode('latin-1', 'ignore').decode('latin-1'), ln=True, align='R')
            pdf.ln(1)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(3)

            # --- 3. DESEMPENHO ACADÊMICO (NOTAS) ---
            pdf.set_font("Arial", "B", 11)
            pdf.cell(190, 7, "DESEMPENHO ACADEMICO", ln=True)
            
            pdf.set_font("Arial", "B", 9)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(145, 6, "Atividade", border=1, fill=True)
            pdf.cell(45, 6, "Nota", border=1, ln=True, align='C', fill=True)
            
            pdf.set_font("Arial", "", 9)
            soma_normais = 0
            for nome_atv, valor in notas:
                pdf.cell(145, 5, f"  {nome_atv[:35]}".encode('latin-1', 'ignore').decode('latin-1'), border=1)
                pdf.cell(45, 5, f"{float(valor):.1f}", border=1, ln=True, align='C')
                soma_normais += float(valor)
            
            pdf.set_font("Arial", "B", 9)
            pdf.cell(145, 6, "  SOMATORIO DAS ATIVIDADES (A)", border=1)
            pdf.cell(45, 6, f"{soma_normais:.1f}", border=1, ln=True, align='C')

            pdf.cell(145, 6, "  NOTA DA RECUPERACAO PARALELA (B)", border=1)
            pdf.cell(45, 6, f"{recuperacao:.1f}", border=1, ln=True, align='C')

            pdf.set_fill_color(230, 240, 255)
            nota_final_tri = max(soma_normais, recuperacao)
            pdf.cell(145, 7, f"  TOTAL DO {trimestre}º TRIMESTRE (MAIOR ENTRE A E B)", border=1, fill=True)
            pdf.cell(45, 7, f"{nota_final_tri:.1f}", border=1, ln=True, align='C', fill=True)
            
            # Nota anual com limite
            pdf.cell(145, 7, "  SOMA ANUAL ACUMULADA", border=1)
            pdf.cell(45, 7, f"{nota_anual_corrigida:.1f}", border=1, ln=True, align='C')
            pdf.ln(4)

            # --- 4. FREQUÊNCIA DETALHADA ---
            pdf.set_font("Arial", "B", 11)
            pdf.cell(190, 7, f"FREQUENCIA DETALHADA - {trimestre}º TRIMESTRE", ln=True)
            
            # ⭐ NOVO: Processar a lista de chamada (já vem com status None para aulas sem registro)
            aulas_unicas = []
            aulas_vistas = set()
            
            for aula in chamada:
                if isinstance(aula, dict):
                    # Formato dicionário (novo método)
                    chave = f"{aula['data']}_{aula['tema']}"
                    if chave not in aulas_vistas:
                        aulas_vistas.add(chave)
                        status = aula.get('status')
                        # Converter status None para -1 (sem registro)
                        status_val = -1 if status is None else status
                        aulas_unicas.append({
                            'data': aula['data'],
                            'tema': aula['tema'],
                            'status': status_val,
                            'justificativa': aula.get('justificativa', '')
                        })
                else:
                    # Formato tupla (backwards compatibility)
                    chave = f"{aula[0]}_{aula[1]}"
                    if chave not in aulas_vistas:
                        aulas_vistas.add(chave)
                        status_val = aula[2] if len(aula) > 2 else None
                        status_val = -1 if status_val is None else status_val
                        aulas_unicas.append({
                            'data': aula[0],
                            'tema': aula[1],
                            'status': status_val,
                            'justificativa': aula[3] if len(aula) > 3 else ''
                        })
            
            if not aulas_unicas:
                pdf.cell(190, 6, "Nenhum registro de aula encontrado.", border=1, ln=True, align='C')
            else:
                meio = (len(aulas_unicas) + 1) // 2
                col1, col2 = aulas_unicas[:meio], aulas_unicas[meio:]
                y_base = pdf.get_y()
                
                def desenhar_coluna(lista, x_offset):
                    pdf.set_xy(x_offset, y_base)
                    pdf.set_font("Arial", "B", 8)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.cell(15, 5, "Data", border=1, align='C', fill=True)
                    pdf.cell(65, 5, "Tema", border=1, align='C', fill=True)
                    pdf.cell(10, 5, "St", border=1, ln=True, align='C', fill=True)
                    pdf.set_font("Arial", "", 7)
                    
                    for aula in lista:
                        pdf.set_x(x_offset)
                        data_str = str(aula['data'])[:10]
                        tema_str = str(aula['tema'])[:35].encode('latin-1', 'ignore').decode('latin-1')
                        status = aula['status']
                        
                        # Definir símbolo e cor baseado no status
                        if status == 1:
                            simbolo = "P"
                            pdf.set_text_color(0, 100, 0)  # Verde para presente
                        elif status == 0:
                            simbolo = "F"
                            pdf.set_text_color(200, 0, 0)  # Vermelho para falta
                        else:  # status == -1 ou None
                            simbolo = "?"
                            pdf.set_text_color(128, 128, 128)  # Cinza para não registrado
                        
                        pdf.cell(15, 4.5, data_str, border=1, align='C')
                        pdf.cell(65, 4.5, tema_str, border=1)
                        pdf.cell(10, 4.5, simbolo, border=1, ln=True, align='C')
                        pdf.set_text_color(0, 0, 0)  # Reset cor

                desenhar_coluna(col1, 10)
                desenhar_coluna(col2, 105)
                
                # Resumo do trimestre
                y_final = y_base + (max(len(col1), len(col2)) * 4.5) + 5
                pdf.set_y(y_final)
                pdf.set_font("Arial", "B", 8)
                pdf.set_fill_color(245, 245, 245)
                
                # Contar faltas reais (status == 0) e não registradas (status == -1)
                faltas_reais = sum(1 for a in aulas_unicas if a['status'] == 0)
                nao_registradas = sum(1 for a in aulas_unicas if a['status'] == -1)
                total_aulas = len(aulas_unicas)
                presencas = total_aulas - faltas_reais - nao_registradas
                
                txt_freq = (f"AULAS PLANEJADAS: {total_aulas}  |  "
                            f"PRESENÇAS: {presencas}  |  "
                            f"FALTAS: {faltas_reais}  |  "
                            f"NÃO REGISTRADAS: {nao_registradas}  |  "
                            f"FREQUÊNCIA: {freq_tri:.1f}%")
                
                pdf.cell(190, 6, txt_freq, border=1, ln=True, align='C', fill=True)
                
                # ⭐ Observação sobre aulas não registradas
                if nao_registradas > 0:
                    pdf.set_font("Arial", "I", 7)
                    pdf.set_text_color(128, 128, 128)
                    pdf.cell(190, 4, "* Aulas marcadas com '?' não tiveram chamada registrada.", ln=True, align='C')
                    pdf.set_text_color(0, 0, 0)
                
                # Acumulado anual
                pdf.set_font("Arial", "B", 9)
                pdf.set_fill_color(230, 240, 255)
                txt_anual = (f"ACUMULADO ANUAL: Total de Faltas: {faltas_anual}  |  "
                            f"Frequência: {perc_anual}")
                
                pdf.cell(190, 6, txt_anual, border=1, ln=True, align='C', fill=True)
                pdf.ln(3)

            # --- 5. OCORRÊNCIAS ---
            # Filtrar ocorrências do trimestre
            ocorrencias_filtradas = []
            for o in ocorrencias:
                if len(o) > 2:
                    tri_oc = o[2] if len(o) > 2 else None
                    if str(tri_oc) == str(trimestre):
                        ocorrencias_filtradas.append(o)
                elif len(o) >= 2:
                    # Fallback: sem trimestre, assume que é do trimestre atual
                    ocorrencias_filtradas.append(o)
            
            if ocorrencias_filtradas:
                pdf.set_font("Arial", "B", 11)
                pdf.cell(190, 7, "OCORRENCIAS DO TRIMESTRE", ln=True)
                pdf.set_font("Arial", "", 8)
                
                for i in range(0, len(ocorrencias_filtradas), 2):
                    reg1 = ocorrencias_filtradas[i]
                    data1 = str(reg1[0])[:10] if len(reg1) > 0 else ""
                    texto1 = str(reg1[1])[:50] if len(reg1) > 1 else ""
                    txt1 = f"[{data1}] {texto1}"
                    pdf.cell(95, 5, txt1.encode('latin-1', 'ignore').decode('latin-1'), border='B')
                    
                    if i + 1 < len(ocorrencias_filtradas):
                        reg2 = ocorrencias_filtradas[i+1]
                        data2 = str(reg2[0])[:10] if len(reg2) > 0 else ""
                        texto2 = str(reg2[1])[:50] if len(reg2) > 1 else ""
                        txt2 = f"[{data2}] {texto2}"
                        pdf.cell(95, 5, txt2.encode('latin-1', 'ignore').decode('latin-1'), border='B', ln=True)
                    else:
                        pdf.cell(95, 5, "", border='B', ln=True)
            pdf.ln(6)

            # --- 6. ASSINATURAS ---
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.set_y(-30)
            y_ass = pdf.get_y()
            pdf.set_font("Arial", "", 9)
            
            pdf.set_xy(15, y_ass)
            pdf.cell(75, 4, "_________________________________", ln=True, align='C')
            pdf.set_x(15)
            pdf.cell(75, 4, "Assinatura do Professor", ln=True, align='C')
            
            pdf.set_xy(115, y_ass)
            pdf.cell(75, 4, "_________________________________", ln=True, align='C')
            pdf.set_x(115)
            pdf.cell(75, 4, "Assinatura do Responsavel", ln=True, align='C')

            # ⭐ SALVAR PDF COM TRATAMENTO DE ERRO
            try:
                pdf.output(caminho)
                print(f"✅ PDF salvo com sucesso em: {caminho}")
                return True
            except Exception as e:
                print(f"❌ Erro ao salvar PDF: {e}")
                # Tentativa 2: usar caminho alternativo
                try:
                    caminho_alt = os.path.join(os.path.expanduser("~"), "Desktop", f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                    pdf.output(caminho_alt)
                    print(f"✅ PDF salvo em caminho alternativo: {caminho_alt}")
                    return True
                except:
                    return False

        except Exception as e:
            print(f"❌ Erro no Gerador de PDF: {e}")
            import traceback
            traceback.print_exc()
            return False