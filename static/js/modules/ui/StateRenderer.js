// StateRenderer.js - Pure rendering helpers that build DOM for game states

export default class StateRenderer {
  constructor() {}

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  createPlayerElement(player, index, currentPlayerId, currentPosition, previousScore) {
    const el = document.createElement('div');
    el.className = `player-item ${player.connected ? 'connected' : 'disconnected'} ${player.player_id === currentPlayerId ? 'current-player' : ''}`;

    // Adjust position for ties
    if (previousScore !== null && player.score < previousScore) {
      currentPosition = index + 1;
    }

    const hasScores = player.score > 0;
    const positionBadge = (hasScores && currentPosition <= 3)
      ? `<span class="position-badge position-${currentPosition}">${currentPosition}</span>`
      : '';

    el.innerHTML = `
      <div class="player-info">
        <div class="player-name-row">
          ${positionBadge}
          <span class="player-name">${this.escapeHtml(player.name)}</span>
        </div>
        <span class="player-score">${player.score} pts</span>
      </div>
      <div class="player-status ${player.connected ? 'online' : 'offline'}">
        ${player.connected ? '●' : '○'}
      </div>
    `;
    return el;
  }

  createResponseCard(response, index, onGuess) {
    const responseCard = document.createElement('div');
    responseCard.className = 'response-card';

    const responseTextWithBreaks = this.escapeHtml(response.text).replace(/\n/g, '<br>');

    responseCard.innerHTML = `
      <div class="response-text">${responseTextWithBreaks}</div>
      <button class="guess-btn btn btn-outline" data-index="${index}">
        This is the bot
      </button>
    `;

    // Hook button
    const guessBtn = responseCard.querySelector('.guess-btn');
    guessBtn.addEventListener('click', (event) => {
      event.preventDefault();
      if (!guessBtn.disabled && typeof onGuess === 'function') {
        onGuess(index, response);
      }
    });

    return responseCard;
  }

  renderCorrectResponse(container, results) {
    if (!container || !results?.correct_response) return;
    const html = `
      <div class="response-header">
        <span class="response-label">Response by <span class="model-highlight">${results.correct_response.model}</span>:</span>
      </div>
      <div class="response-text">${this.escapeHtml(results.correct_response.text).replace(/\n/g, '<br>')}</div>
    `;
    container.innerHTML = html;
  }

  renderPlayerResults(container, results, escapeHtml = (t) => this.escapeHtml(t)) {
    if (!container || !results?.player_results) return;
    container.innerHTML = '';

    const playerArray = Object.values(results.player_results).sort((a, b) => b.round_points - a.round_points);
    playerArray.forEach((player) => {
      const scoreItem = document.createElement('div');
      scoreItem.className = 'score-item';

      // Build voted text
      let votedForText = '';
      if (player.guess_target !== null && player.guess_target !== undefined) {
        if (player.guess_target === results.llm_response_index) {
          votedForText = 'Voted: 🤖 (AI)';
        } else {
          const votedResponse = results.responses[player.guess_target];
          if (votedResponse && votedResponse.author_name) {
            votedForText = `Voted: ${escapeHtml(votedResponse.author_name)}`;
          } else {
            votedForText = 'Voted: Unknown';
          }
        }
      } else {
        votedForText = 'No vote';
      }

      const details = [];
      if (player.correct_guess) details.push('Correct guess: +1 pt');
      if (player.deception_points > 0) {
        const voteCount = player.response_votes;
        details.push(`Fooled ${voteCount} player${voteCount !== 1 ? 's' : ''}: +${player.deception_points} pts`);
      }
      if (details.length === 0) details.push('No points this round');

      scoreItem.innerHTML = `
        <div class="player-result">
          <div class="player-header">
            <span class="player-name">${escapeHtml(player.name)}</span>
            <span class="round-points">+${player.round_points} pts</span>
          </div>
          <div class="player-details">
            <div class="vote-info">${votedForText}</div>
            <div class="votes-received">Votes received: ${player.response_votes}</div>
            <div class="scoring-breakdown">${details.join(' • ')}</div>
          </div>
        </div>
      `;
      container.appendChild(scoreItem);
    });
  }
}
