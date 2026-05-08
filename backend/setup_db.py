import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    print("❌ ERROR: DATABASE_URL not found in .env")
    exit(1)

def setup():
    print(f"Connecting to {DB_URL.split('@')[1]}...")
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    print("Creating table 'notas'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS public.notas (
        id SERIAL PRIMARY KEY,
        user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
        chave VARCHAR(44) UNIQUE NOT NULL,
        emitente TEXT,
        cnpj VARCHAR(18),
        data_emissao TEXT,
        numero TEXT,
        valor_total DECIMAL(10, 2),
        total_itens INTEGER,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    print("Creating table 'produtos'...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS public.produtos (
        id SERIAL PRIMARY KEY,
        nota_id INTEGER REFERENCES public.notas(id) ON DELETE CASCADE,
        codigo TEXT,
        nome TEXT,
        qtd DECIMAL(10, 3),
        unidade VARCHAR(10),
        valor_unitario DECIMAL(10, 2),
        valor_total DECIMAL(10, 2)
    );
    """)

    print("Setting up Row Level Security (RLS)...")
    
    # Enable RLS on both tables
    cursor.execute("ALTER TABLE public.notas ENABLE ROW LEVEL SECURITY;")
    cursor.execute("ALTER TABLE public.produtos ENABLE ROW LEVEL SECURITY;")
    
    # Create policies for notas
    cursor.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Usuarios veem apenas suas notas') THEN
            CREATE POLICY "Usuarios veem apenas suas notas" ON public.notas
            FOR ALL USING (auth.uid() = user_id);
        END IF;
    END
    $$;
    """)

    # Create policies for produtos
    cursor.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Usuarios veem apenas produtos de suas notas') THEN
            CREATE POLICY "Usuarios veem apenas produtos de suas notas" ON public.produtos
            FOR ALL USING (
                EXISTS (
                    SELECT 1 FROM public.notas n 
                    WHERE n.id = public.produtos.nota_id 
                    AND n.user_id = auth.uid()
                )
            );
        END IF;
    END
    $$;
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Database setup complete!")

if __name__ == "__main__":
    setup()
