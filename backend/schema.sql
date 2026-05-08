-- Criar tabela de notas
CREATE TABLE IF NOT EXISTS public.notas (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    chave VARCHAR(44) UNIQUE NOT NULL,
    emitente TEXT,
    cnpj VARCHAR(18),
    endereco TEXT,
    data_emissao TEXT,
    numero TEXT,
    valor_total DECIMAL(10, 2),
    url TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dados_json TEXT
);

-- Criar tabela de produtos
CREATE TABLE IF NOT EXISTS public.produtos (
    id SERIAL PRIMARY KEY,
    nota_id INTEGER REFERENCES public.notas(id) ON DELETE CASCADE,
    nome TEXT,
    qtd DECIMAL(10, 3),
    valor_unitario DECIMAL(10, 2),
    valor_total DECIMAL(10, 2)
);

-- Habilitar a Segurança em Nível de Linha (RLS)
ALTER TABLE public.notas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.produtos ENABLE ROW LEVEL SECURITY;

-- Política: Usuários só podem ver/inserir/deletar SUAS próprias notas
CREATE POLICY "Isolamento de Notas por Usuario" ON public.notas
    FOR ALL USING (auth.uid() = user_id);

-- Política: Usuários só podem ver/inserir/deletar produtos de SUAS notas
CREATE POLICY "Isolamento de Produtos por Usuario" ON public.produtos
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.notas n 
            WHERE n.id = public.produtos.nota_id 
            AND n.user_id = auth.uid()
        )
    );
