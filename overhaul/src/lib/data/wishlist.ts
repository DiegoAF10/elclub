// Mirror of Rust WishlistItem struct (lib.rs · R2 section)
export interface WishlistItem {
  wishlist_item_id:      number;
  family_id:             string;
  jersey_id:             string | null;
  size:                  string | null;
  player_name:           string | null;
  player_number:         number | null;
  patch:                 string | null;
  version:               string | null;
  customer_id:           string | null;
  expected_usd:          number | null;
  status:                'active' | 'promoted' | 'cancelled';
  promoted_to_import_id: string | null;
  created_at:            string;
  notes:                 string | null;
}

export const WISHLIST_TARGET_SIZE = 20; // D-Settings default per spec sec 4.6

export function statusLabel(status: WishlistItem['status']): string {
  switch (status) {
    case 'active':    return '● ACTIVE';
    case 'promoted':  return '● PROMOTED';
    case 'cancelled': return '● CANCELLED';
  }
}

export function isAssigned(item: WishlistItem): boolean {
  return item.customer_id !== null && item.customer_id !== '';
}
