# Nubank Classification Mappings

## Column Layout (Dump de fatura)
1. **Data da despesa**: Column A
2. **Ano e mês da despesa**: Column B (Normalized to 1st)
3. **Quem gastou?**: Column C
4. **Pago por quem?**: Column D
5. **Categoria**: Column E
6. **Subcategoria**: Column F
7. **Subgrupo**: Column G
8. **Frequência**: Column H
9. **Importância**: Column I
10. **Adiamento de pagamento**: Column J (Value: 1)
11. **Ano e mês de pagamento**: Column K (Normalized to 1st, 1 month offset)
12. **Valor**: Column L
13. **Parcela atual**: Column M
14. **Parcelas totais**: Column N
15. **Descrição**: Column O

## Mappings

| Title Pattern | Categoria | Subcategoria | Subgrupo |
| :--- | :--- | :--- | :--- |
| `Ifd*` (Restaurant names) | Alimentação | Restaurante | Ifood |
| `Ifd*` (Markets/Coop) | Alimentação | Mercado | Ifood |
| `Dl *Uberrides` | Transporte | Táxi | Uber |
| `Dl*99 Ride` | Transporte | Táxi | 99 |
| `Tokio Marine*Auto` | Carro | Seguro | Tokio Marine |
| `Tokio Marine*Resi` | Casa | Seguro | Tokio Marine |
| `Crunchyroll` | Lazer | Streaming | Crunchyroll |
| `Amazonprimebr` | Lazer | Streaming | Amazon Prime |
| `Wellhub` | Cuidados Pessoais | Gympass | Wellhub |
| `Shell Box` | Transporte | Combustível | Shell Box |
| `Petz` | Pet | Mercado | Petz |
| `NuTag*` | Transporte | Pedágio | NuTag |
| `Plano NuCel` | Outros | Celular | NuCel |
| `Samsung` | Eletrônicos | - | Samsung |
| `Academia Samadi` | Cuidados Pessoais | Gym | - |
| `Decolar` | Lazer | Viagem | Decolar |
| `Biteli Pneus` | Carro | Manutenção | - |
| `Montreal-Moda` | Vestuário | Roupas | Montreal |

## General Rules
- **Quem gastou?**: Set to "Ambos" by default for shared expenses. Set to **"Filhos"** when the purchase is clearly for children (e.g., toy stores like `Ri Happy`, kids clothing). "Filhos" is **NOT** a valid Categoria — it is only a value for "Quem gastou?".
- **Pago por quem?**: Set to "Lucas".
- **Frequência**: Default to "Ocasional". Never use empty string.
- **Importância**: Default to "Normal". Never use empty string.
- **Adiamento de pagamento**: Always set to **1**.
- **Ano e mês de pagamento**: 
  - Always normalize to the **1st day of the month**.
  - For the **first installment**, the payment date must be **one month later** than the "Ano e mês da despesa".
- **Installments**: 
  - **Filter**: If a transaction is a 2nd installment or later (e.g., "Parcela 2/10", "Parcela 3/5"), **discard it**.
  - **Filter (Static)**: Discard static recurring or non-purchase entries: `Tokio Marine`, `Come And Se`, `Crunchyroll`, `Amazonprimebr`, `PetLove`, `Meli+`, `Plano NuCel`, `Wellhub`, and `Pagamento recebido`.
  - If a transaction is the first installment (e.g., "Parcela 1/X"), expand it into **X separate rows**.
  - Each row must have an incremented `Parcela atual` and `Ano e mês de pagamento`.
