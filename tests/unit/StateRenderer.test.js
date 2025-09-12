import { describe, it, expect, beforeEach } from 'vitest';

const StateRenderer = (await import('../../static/js/modules/ui/StateRenderer.js')).default;

describe('StateRenderer', () => {
  let renderer;

  beforeEach(() => {
    // jsdom environment already provided by vitest config
    document.body.innerHTML = '';
    renderer = new StateRenderer();
  });

  it('escapeHtml should escape special characters', () => {
    const input = `<script>alert('x')</script>&"'`;
    const out = renderer.escapeHtml(input);
    expect(out).not.toContain('<script>');
    expect(out).toContain('&lt;script&gt;');
    expect(out).toContain('&amp;');
  });

  it('createPlayerElement renders player with proper classes and content', () => {
    const player = { name: 'Alice', score: 10, connected: true, player_id: 'p1' };
    const el = renderer.createPlayerElement(player, 0, 'p1', 1, null);
    expect(el.className).toContain('player-item');
    expect(el.className).toContain('connected');
    expect(el.className).toContain('current-player');
    expect(el.querySelector('.player-name').textContent).toBe('Alice');
    expect(el.querySelector('.player-score').textContent).toContain('10');
  });

  it('createResponseCard wires guess button callback', () => {
    const onGuess = (idx, resp) => {
      // simple callback
    };
    const spy = vi.fn(onGuess);
    const card = renderer.createResponseCard({ text: 'Hello' }, 2, spy);
    const btn = card.querySelector('.guess-btn');
    btn.click();
    expect(spy).toHaveBeenCalledWith(2, { text: 'Hello' });
  });

  it('renderCorrectResponse injects correct response markup', () => {
    const container = document.createElement('div');
    renderer.renderCorrectResponse(container, { correct_response: { text: 'OK', model: 'GPT-4' } });
    expect(container.innerHTML).toContain('Response by');
    expect(container.innerHTML).toContain('GPT-4');
    expect(container.innerHTML).toContain('OK');
  });

  it('renderPlayerResults lists player results with breakdown', () => {
    const container = document.createElement('div');
    const results = {
      llm_response_index: 1,
      responses: [{}, { author_name: 'AI' }, { author_name: 'Bob' }],
      player_results: {
        a: { name: 'Alice', round_points: 2, correct_guess: true, response_votes: 1, deception_points: 0, guess_target: 1 },
        b: { name: 'Bob', round_points: 1, correct_guess: false, response_votes: 2, deception_points: 2, guess_target: 2 },
      },
    };
    renderer.renderPlayerResults(container, results);
    expect(container.querySelectorAll('.score-item').length).toBe(2);
    expect(container.innerHTML).toContain('Alice');
    expect(container.innerHTML).toContain('Bob');
  });
});
