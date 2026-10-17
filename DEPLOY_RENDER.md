# Publicar TradePulse Pro no GitHub + Render

Este projeto é uma aplicação multipáginas estática. O `render.yaml` configura uma hospedagem estática gratuita no Render, com deploy automático quando a branch `main` for atualizada.

## 1. Criar o repositório

1. Crie um repositório chamado `tradepulse-pro` no GitHub. Pode ser privado, desde que o Render tenha acesso a ele.
2. Para evitar conflitos, crie-o vazio (sem README, licença ou `.gitignore` inicial).
3. Extraia a pasta `TradePulsePro` deste pacote e abra um terminal dentro dela.

## 2. Enviar os arquivos

Execute os comandos abaixo; substitua `USUARIO` pelo seu nome de usuário do GitHub e confirme que o endereço é o repositório que você criou:

```bash
git init -b main
git add .
git commit -m "Publica TradePulse Pro"
git remote add origin https://github.com/USUARIO/tradepulse-pro.git
git push -u origin main
```

Se a pasta já tiver um repositório Git inicializado, não execute `git init` novamente. Configure ou verifique o remote com `git remote -v`.

## 3. Criar o site no Render

1. Abra o Render Dashboard e conecte o GitHub, autorizando acesso ao repositório `tradepulse-pro`.
2. Crie um novo **Blueprint** e selecione o repositório.
3. O Render encontrará `render.yaml`; revise o serviço `tradepulse-pro` e aplique a configuração.
4. Aguarde o deploy ficar `Live`. A URL pública será exibida na página do serviço.

## O que funciona no site estático

As páginas de painel, gestão de risco, alertas, simulador, backtesting, desempenho e testes de dados públicos funcionam como aplicação cliente, usando o mesmo domínio e `localStorage` do navegador.

Os alertas só são monitorados enquanto a página está aberta. O armazenamento é local ao navegador/dispositivo e não sincroniza entre aparelhos.

## Segurança e limitações

- O site publicado é estático; ele **não ativa** o endpoint privado `/api/account` da Binance. Essa opção só funciona com o servidor local `server.py` configurado. Não publique um backend de conta privada sem adicionar autenticação, proteção contra abuso, política de origem e gestão segura das credenciais.
- Não coloque API keys, secrets, tokens, `.env` nem credenciais nos arquivos HTML ou no repositório.
- A integração de mercado usa APIs públicas externas e depende da disponibilidade delas.
