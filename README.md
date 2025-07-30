# Sistema de Gestão Inteligente para Contratadas (SEGMA-SIS)

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)
![Tecnologia](https://img.shields.io/badge/backend-Python%20%7C%20Streamlit-blue)
![IA](https://img.shields.io/badge/IA-Google%20Gemini-orange)

**Automatize a conformidade, reduza riscos e gerencie a documentação de seus prestadores de serviço com o poder da Inteligência Artificial.**

---

## O Problema

Gerenciar a documentação de Saúde e Segurança do Trabalho (SST) de empresas contratadas é um desafio complexo, manual e propenso a falhas. Controlar vencimentos de ASOs, validar certificados de NRs e garantir a conformidade de PGRs e PCMSOs consome tempo, recursos e expõe a empresa a riscos legais e operacionais significativos.

## A Solução: SEGMA-SIS

O **SEGMA-SIS** é uma plataforma inteligente que centraliza e automatiza a gestão de documentos de SST de contratadas. Utilizando a IA avançada do Google Gemini, o sistema não apenas armazena documentos, mas os analisa, audita e transforma dados em ações, garantindo um novo nível de controle e segurança.

---

## Principais Funcionalidades

*   **🗂️ Central de Documentos:** Um repositório único e organizado para toda a documentação de empresas, funcionários, ASOs, treinamentos e fichas de EPI.

*   **🧠 Análise Inteligente com IA:** Faça o upload de um PDF e deixe a IA trabalhar. O sistema extrai automaticamente informações cruciais como datas de emissão, vencimentos, nomes, tipos de exame e cargas horárias, eliminando a digitação manual.

*   **⚖️ Auditoria de Conformidade Automatizada:** No momento do upload, cada documento é submetido a uma auditoria instantânea. Usando uma base de conhecimento (RAG), a IA verifica se o documento atende aos requisitos normativos (NRs) e aponta inconsistências, como cargas horárias insuficientes ou datas inválidas.

*   **📋 Geração Automática de Plano de Ação:** Uma não conformidade foi encontrada? O SEGMA-SIS cria automaticamente um item no Plano de Ação, vinculando o problema ao documento e ao funcionário, garantindo que nenhuma pendência seja esquecida.

*   **🗓️ Dashboard de Gestão:** Visualize o status de todos os documentos e funcionários de uma empresa em uma única tela. Monitore vencimentos, trate pendências e consulte o histórico completo de auditorias com status de tratamento.

*   **📧 Notificador Automático de Vencimentos:** Um sistema proativo envia relatórios por e-mail, alertando sobre documentos vencidos ou próximos do vencimento, permitindo ações preventivas.

---

## Demonstração Visual

**1. Upload e Análise Instantânea**
`![GIF de Análise de ASO](link_para_seu_gif_1.gif)`

**2. Auditoria e Criação de Plano de Ação**
`![GIF de Auditoria e Plano de Ação](link_para_seu_gif_2.gif)`

**3. Gestão e Tratamento de Pendências**
`![GIF de Tratamento de Pendência](link_para_seu_gif_3.gif)`

---

## Tecnologias Utilizadas

*   **Frontend:** Streamlit
*   **Backend & Lógica de Negócio:** Python
*   **Inteligência Artificial:** Google Gemini (para extração e RAG)
*   **Banco de Dados:** Google Sheets
*   **Armazenamento de Arquivos:** Google Drive

---

## Contato e Demonstração

Este é um projeto proprietário e não está disponível para uso público ou redistribuição.

Para uma **demonstração ao vivo** ou para discutir como o SEGMA-SIS pode ser adaptado para as necessidades da sua empresa, entre em contato:

*   **Autor:** Cristian Ferreira Carlos
*   **LinkedIn:** [https://www.linkedin.com/in/cristian-ferreira-carlos-256b19161/](https://www.linkedin.com/in/cristian-ferreira-carlos-256b19161/)
*   **E-mail:** cristianfc2015@hotmail.com

---

## Licença de Uso

Este software é uma propriedade intelectual de Cristian Ferreira Carlos. Todos os direitos são reservados.

É estritamente proibido o uso, cópia, modificação, fusão, publicação, distribuição, sublicenciamento e/ou venda de cópias do Software sem a permissão expressa e por escrito do autor. Para mais detalhes, consulte o arquivo `LICENSE.txt`.
