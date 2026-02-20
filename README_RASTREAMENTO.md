# Rastreamento de Leads (Origem de Tráfego)

Este documento explica como identificar de onde vieram os leads (Instagram, WhatsApp, Facebook, etc.) ao usar o Vizô hospedado na Hostinger.

## Como funciona?

O sistema foi atualizado para ler parâmetros da URL (o endereço do site). Isso significa que você pode criar links diferentes para cada rede social, e o Vizô saberá automaticamente de onde a pessoa veio.

## Exemplos de Links para Divulgação

Supondo que seu site seja `https://provisaomacapa.com.br/chat.html`:

### 1. Instagram (Bio ou Stories)
Use este link:
`https://provisaomacapa.com.br/chat.html?source=instagram`

### 2. Facebook (Posts ou Anúncios)
Use este link:
`https://provisaomacapa.com.br/chat.html?source=facebook`

### 3. WhatsApp (Status ou Mensagens)
Use este link:
`https://provisaomacapa.com.br/chat.html?source=whatsapp`

### 4. Google Ads (Campanhas Pagas)
Você pode ser ainda mais específico usando parâmetros UTM (padrão de marketing):
`https://provisaomacapa.com.br/chat.html?utm_source=google&utm_campaign=lentes_evo`

## Como ver os dados?

Atualmente, o sistema registra essas informações no **Console do Navegador** (para desenvolvedores) e prepara o envio para um banco de dados.

Quando um cliente inicia o chat, o sistema registra:
```json
[METRICS] SESSION_START {
  "source": "instagram",
  "medium": "unknown",
  "campaign": "unknown",
  "referrer": "direct"
}
```

Quando o cliente converte (informa o WhatsApp), o sistema anexa a origem ao cadastro:
```json
[METRICS] LEAD_CONVERTED {
  "nome": "João da Silva",
  "whatsapp": "96991234567",
  "source": "instagram"
}
```

## Próximos Passos na Hostinger

Para salvar esses dados permanentemente, você precisará de um pequeno script de backend (PHP ou Python) na Hostinger para receber esses logs e salvar em um banco de dados MySQL ou arquivo de texto.
