# Sistema de Gestão de Documentação de Contratadas (SEGMA-SIS)

Sistema desenvolvido para gerenciar documentação de empresas contratadas, incluindo ASOs (Atestados de Saúde Ocupacional) e treinamentos de normas regulamentadoras (NRs).

## Funcionalidades

### Gestão de Empresas
- Cadastro de empresas contratadas
- Visualização de dados por empresa
- Gerenciamento de funcionários por empresa

### Gestão de Documentos
- Upload e análise automática de ASOs
  - Extração automática de datas
  - Identificação de riscos ocupacionais
  - Validação de vencimentos
  - Armazenamento seguro no Google Drive

- Gestão de Treinamentos de NRs
  - Suporte às normas: NR-10, NR-18, NR-20, NR-34, NR-35
  - Análise automática de certificados
  - Validação de cargas horárias e periodicidades
  - Controle de vencimentos

### Normas Regulamentadoras Suportadas

#### NR-20
##### Reciclagem:
| Módulo | Periodicidade | Carga Horária Mínima |
|--------|---------------|---------------------|
| Básico | 3 anos | 4 horas |
| Intermediário | 2 anos | 4 horas |
| Avançado I | 1 ano | 4 horas |
| Avançado II | 1 ano | 4 horas |

##### Formação Inicial:
| Módulo | Carga Horária Mínima |
|--------|---------------------|
| Básico | 8 horas |
| Intermediário | 16 horas |
| Avançado I | 32 horas |
| Avançado II | 40 horas |

#### Outras NRs
| Norma | Carga Horária Inicial | Carga Horária Reciclagem | Periodicidade Reciclagem |
|-------|----------------------|------------------------|----------------------|
| NR-35 | 8 horas | 8 horas | 2 anos |
| NR-10 | 40 horas | 40 horas | 2 anos |
| NR-18 | 8 horas | 8 horas | 1 ano |
| NR-34 | 8 horas | 8 horas | 1 ano |

## Tecnologias Utilizadas

- **Frontend**: Streamlit
- **Backend**: Python
- **Banco de Dados**: Google Sheets
- **Armazenamento**: Google Drive
- **IA**: Modelo Gemini para análise de documentos

## Requisitos

```bash
pip install -r requirements.txt
```

## Estrutura do Projeto

```
segma_sis/
├── AI/                     # Módulos de inteligência artificial
├── auth/                   # Configurações de autenticação
├── data/                   # Dados e configurações
├── gdrive/                 # Integração com Google Drive
├── operations/             # Lógica de negócio
│   ├── employee.py        # Gestão de funcionários
│   ├── front.py           # Interface do usuário
│   └── sheet.py           # Operações com planilhas
├── main.py                # Ponto de entrada da aplicação
├── requirements.txt       # Dependências do projeto
└── README.md             # Este arquivo
```

## Configuração

1. Configure as credenciais do Google:
   - Crie um projeto no Google Cloud Console
   - Habilite as APIs do Google Drive e Google Sheets
   - Configure as credenciais de autenticação

2. Configure o arquivo de ambiente:
   - Copie o arquivo `.env.example` para `.env`
   - Preencha as variáveis de ambiente necessárias

## Uso

1. Execute o aplicativo:
```bash
streamlit run main.py
```

2. Fluxo básico:
   - Selecione ou cadastre uma empresa
   - Visualize os dados existentes na aba "Dados da Empresa"
   - Cadastre novos funcionários se necessário
   - Adicione documentos na aba "Adicionar Documentos"

## Recursos

- Interface intuitiva para gestão de documentos
- Análise automática de PDFs
- Validação automática de normas
- Armazenamento seguro de documentos
- Controle de vencimentos
- Visualização organizada por empresa

## Contribuição

1. Faça um Fork do projeto
2. Crie uma Branch para sua Feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a Branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE.txt](LICENSE.txt) para detalhes.

## Suporte

Para suporte, envie um email para [seu-email@exemplo.com] ou abra uma issue no GitHub. 