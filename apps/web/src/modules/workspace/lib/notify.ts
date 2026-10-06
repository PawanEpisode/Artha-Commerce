import { toast } from '@artha/design-system'

export const notify = {
  setupCardHidden: () => toast.info('You can finish setup from your workspace any time.', { id: 'setup-card-hidden' }),
}
