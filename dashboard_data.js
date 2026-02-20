// Dados simulados para o Dashboard Vizô
    const dashboardData = {
        // Dados específicos por rede social
        social: {
            instagram: {
                totalLeads: 450,
                conversionRate: 35.5,
                dailyGrowth: 15, // leads hoje
                topInterest: "Lentes EVO",
                recentLeads: [
                    { name: "Maria Silva", time: "10:30", status: "Novo Lead", phone: "96 99100-1234", type: "Lentes EVO" },
                    { name: "Carla Dias", time: "09:15", status: "Agendado", phone: "96 98111-2233", type: "Consulta" }
                ],
                chartData: [40, 30, 20, 10] // Consulta, Exame, Cirurgia, Outros
            },
            whatsapp: {
                totalLeads: 320,
                conversionRate: 42.0,
                dailyGrowth: 22,
                topInterest: "Consulta Rotina",
                recentLeads: [
                    { name: "João Souza", time: "09:45", status: "Agendado", phone: "96 98111-5566", type: "Consulta" },
                    { name: "Pedro Lima", time: "08:30", status: "Novo Lead", phone: "96 99988-7766", type: "Exames" }
                ],
                chartData: [60, 25, 10, 5]
            },
            facebook: {
                totalLeads: 150,
                conversionRate: 28.5,
                dailyGrowth: 8,
                topInterest: "Cirurgia Catarata",
                recentLeads: [
                    { name: "Ana Paula", time: "Ontem", status: "Novo Lead", phone: "96 99122-3344", type: "Cirurgia" },
                    { name: "Roberto Alves", time: "Ontem", status: "Agendado", phone: "96 98877-6655", type: "Cirurgia" }
                ],
                chartData: [20, 20, 50, 10]
            }
        },

        // Visão Geral
    overview: {
        totalLeads: 1248,
        conversions: 387,
        conversionRate: 31.0,
        avgWaitTime: "45s", // Tempo médio de espera
        avgHandleTime: "3m 12s", // Tempo médio de atendimento
        activeChats: 12
    },
    
    // Funil de Conversão (Leads -> Agendamentos -> Confirmados)
    funnel: {
        leads: 1248,
        interactions: 1050,
        schedulingStarted: 620,
        appointments: 387,
        confirmed: 350
    },

    // Distribuição por Tipo de Solicitação
    requestTypes: {
        labels: ["Agendamento", "Exames", "Cirurgias", "Especialistas", "Outros"],
        data: [45, 25, 15, 10, 5]
    },

    // Origem dos Leads (Rastreamento)
    leadSources: {
        labels: ["Instagram", "WhatsApp", "Facebook", "Site Direto", "Google Ads", "Outros"],
        data: [450, 320, 150, 200, 120, 50],
        colors: ['#E1306C', '#25D366', '#1877F2', '#2e70ce', '#FBBC05', '#6b7280']
    },

    // Performance Diária (Últimos 7 dias)
    dailyPerformance: {
        labels: ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
        leads: [150, 180, 160, 190, 210, 120, 80],
        conversions: [45, 55, 50, 60, 75, 40, 25]
    },

    // Tempo Médio por Etapa (segundos)
    stepTimes: {
        labels: ["Saudação", "Menu", "Coleta Dados", "Escolha Médico", "Finalização"],
        data: [5, 12, 45, 20, 15]
    },

    // Tabela de Leads Recentes (Mock)
    recentLeads: [
        { name: "Maria Silva", time: "10:30", status: "Novo Lead", phone: "96 99100-1234", type: "Consulta", source: "Instagram" },
        { name: "João Souza", time: "09:45", status: "Agendado", phone: "96 98111-5566", type: "Exames", source: "WhatsApp" },
        { name: "Ana Paula", time: "09:15", status: "Novo Lead", phone: "96 99122-3344", type: "Lentes", source: "Facebook" },
        { name: "Pedro Santos", time: "Ontem", status: "Agendado", phone: "96 98877-6655", type: "Cirurgia", source: "Site Direto" },
        { name: "Lucia Lima", time: "Ontem", status: "Novo Lead", phone: "96 99988-7744", type: "Consulta", source: "Google Ads" }
    ],
    
    // Novos dados para análise avançada
    advancedMetrics: {
        churn: {
            labels: ['Início Conversa', 'Menu Principal', 'Solicitou Nome', 'Informou WhatsApp', 'Agendamento Final'],
            data: [100, 85, 60, 45, 38] // Percentual de retenção
        },
        doctorRanking: [
            { name: "Dr. Lucas Rezende", count: 145, rating: 4.9 },
            { name: "Dra. Ana Catarina", count: 132, rating: 5.0 },
            { name: "Dr. Tarcísio Guerra", count: 98, rating: 4.8 },
            { name: "Dra. Nabila Demachki", count: 87, rating: 4.9 },
            { name: "Dra. Roseni Lopes", count: 76, rating: 4.7 }
        ],
        interests: {
            labels: ['Consultas', 'Exames Rotina', 'Cirurgia Catarata', 'Lentes EVO', 'Urgência'],
            data: [450, 300, 150, 80, 20]
        },
        heatmap: {
            // Intensidade de 0 a 100
            days: ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'],
            hours: ['08-10h', '10-12h', '14-16h', '16-18h', '18-20h'],
            data: [
                [20, 80, 60, 90, 40], // Seg
                [30, 85, 55, 95, 50], // Ter
                [25, 75, 50, 85, 45], // Qua
                [20, 70, 45, 80, 40], // Qui
                [15, 60, 40, 70, 30], // Sex
                [10, 40, 20, 10, 5]   // Sáb
            ]
        }
    }
};
