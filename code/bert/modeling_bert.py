import math
from transformers import BertPreTrainedModel
import torch
from torch import nn
from packaging import version
from transformers.modeling_utils import (
    apply_chunking_to_forward,
    find_pruneable_heads_and_indices,
    prune_linear_layer,
)
from transformers.activations import ACT2FN
from transformers.utils import logging
from transformers.modeling_outputs import (
    BaseModelOutputWithPastAndCrossAttentions,
    BaseModelOutputWithPoolingAndCrossAttentions,
)
import torch.utils.checkpoint
logger = logging.get_logger(__name__)

#
# class BertEmbeddings(nn.Module):
#     """Construct the embeddings from word, position and token_type embeddings."""
#
#     def __init__(self, config):
#         super().__init__()
#         self.word_embeddings = nn.Embedding(config.vocab_size, config.hidden_size, padding_idx=config.pad_token_id)
#         self.position_embeddings = nn.Embedding(config.max_position_embeddings, config.hidden_size)
#         self.token_type_embeddings = nn.Embedding(config.type_vocab_size, config.hidden_size)
#
#         # self.LayerNorm is not snake-cased to stick with TensorFlow model variable name and be able to load
#         # any TensorFlow checkpoint file
#         self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
#         self.dropout = nn.Dropout(config.hidden_dropout_prob)
#         # position_ids (1, len position emb) is contiguous in memory and exported when serialized
#         self.position_embedding_type = getattr(config, "position_embedding_type", "absolute")
#         self.register_buffer("position_ids", torch.arange(config.max_position_embeddings).expand((1, -1)))
#         if version.parse(torch.__version__) > version.parse("1.6.0"):
#             self.register_buffer(
#                 "token_type_ids",
#                 torch.zeros(self.position_ids.size(), dtype=torch.long),
#                 persistent=False,
#             )
#
#     def forward(
#         self, input_ids=None, token_type_ids=None, position_ids=None, inputs_embeds=None, past_key_values_length=0,
#             character_level_ids=None, word_level_ids=None, grammar_level_ids=None
#     ):
#         if input_ids is not None:
#             input_shape = input_ids.size()
#         else:
#             input_shape = inputs_embeds.size()[:-1]
#
#         seq_length = input_shape[1]
#
#         if position_ids is None:
#             position_ids = self.position_ids[:, past_key_values_length : seq_length + past_key_values_length]
#
#         # Setting the token_type_ids to the registered buffer in constructor where it is all zeros, which usually occurs
#         # when its auto-generated, registered buffer helps users when tracing the model without passing token_type_ids, solves
#         # issue #5664
#         if token_type_ids is None:
#             if hasattr(self, "token_type_ids"):
#                 buffered_token_type_ids = self.token_type_ids[:, :seq_length]
#                 buffered_token_type_ids_expanded = buffered_token_type_ids.expand(input_shape[0], seq_length)
#                 token_type_ids = buffered_token_type_ids_expanded
#             else:
#                 token_type_ids = torch.zeros(input_shape, dtype=torch.long, device=self.position_ids.device)
#
#         if inputs_embeds is None:
#             inputs_embeds = self.word_embeddings(input_ids)
#         token_type_embeddings = self.token_type_embeddings(token_type_ids)
#
#         embeddings = inputs_embeds + token_type_embeddings
#         if self.position_embedding_type == "absolute":
#             position_embeddings = self.position_embeddings(position_ids)
#             embeddings += position_embeddings
#         embeddings = self.LayerNorm(embeddings)
#         embeddings = self.dropout(embeddings)
#         return embeddings
#
# class BertEmbeddings_ling(nn.Module):
#     '''
#     For fusing the linguistic features in the Embedding Layer.
#     '''
#     def __init__(self, config):
#         super().__init__()
#         self.word_embeddings = nn.Embedding(config.vocab_size, config.hidden_size, padding_idx=config.pad_token_id)
#         self.position_embeddings = nn.Embedding(config.max_position_embeddings, config.hidden_size)
#         self.token_type_embeddings = nn.Embedding(config.type_vocab_size, config.hidden_size)
#         self.hidden_size = config.hidden_size
#         self.with_character_level_embedding_layer = config.with_character_level_embedding_layer
#         self.with_word_level_embedding_layer = config.with_word_level_embedding_layer
#         self.with_grammar_level_embedding_layer = config.with_grammar_level_embedding_layer
#         self.character_level_embedddings = nn.Embedding(config.character_level_size_embedding_layer, config.hidden_size)
#         self.word_level_embedddings = nn.Embedding(config.word_level_size_embedding_layer, config.hidden_size)
#         self.grammar_level_embedddings = nn.Embedding(config.grammar_level_size_embedding_layer, config.hidden_size)
#         print('with_character_level_embedding_layer: ' + str(self.with_character_level_embedding_layer))
#         print('with_word_level_embedding_layer: ' + str(self.with_word_level_embedding_layer))
#         print('with_grammar_level_embedding_layer: ' + str(self.with_grammar_level_embedding_layer))
#
#         # self.LayerNorm is not snake-cased to stick with TensorFlow model variable name and be able to load
#         # any TensorFlow checkpoint file
#         self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
#         self.dropout = nn.Dropout(config.hidden_dropout_prob)
#         # position_ids (1, len position emb) is contiguous in memory and exported when serialized
#         self.position_embedding_type = getattr(config, "position_embedding_type", "absolute")
#         self.register_buffer("position_ids", torch.arange(config.max_position_embeddings).expand((1, -1)))
#         if version.parse(torch.__version__) > version.parse("1.6.0"):
#             self.register_buffer(
#                 "token_type_ids",
#                 torch.zeros(self.position_ids.size(), dtype=torch.long),
#                 persistent=False,
#             )
#
#     def forward(
#             self, input_ids=None, token_type_ids=None, position_ids=None, inputs_embeds=None, past_key_values_length=0,
#             character_level_ids=None, word_level_ids=None, grammar_level_ids=None
#     ):
#         if input_ids is not None:
#             input_shape = input_ids.size()
#         else:
#             input_shape = inputs_embeds.size()[:-1]
#
#         seq_length = input_shape[1]
#
#         if position_ids is None:
#             position_ids = self.position_ids[:, past_key_values_length: seq_length + past_key_values_length]
#
#         if token_type_ids is None:
#             if hasattr(self, "token_type_ids"):
#                 buffered_token_type_ids = self.token_type_ids[:, :seq_length]
#                 buffered_token_type_ids_expanded = buffered_token_type_ids.expand(input_shape[0], seq_length)
#                 token_type_ids = buffered_token_type_ids_expanded
#             else:
#                 token_type_ids = torch.zeros(input_shape, dtype=torch.long, device=self.position_ids.device)
#
#         if inputs_embeds is None:
#             inputs_embeds = self.word_embeddings(input_ids)
#
#         token_type_embeddings = self.token_type_embeddings(token_type_ids)
#
#         size = (input_ids.shape[0], input_ids.shape[1], self.hidden_size)
#         if self.with_character_level_embedding_layer == "True":
#             character_level_embedddings = self.character_level_embedddings(character_level_ids)
#         else:
#             character_level_embedddings = torch.zeros(size, device=self.position_ids.device)
#         if self.with_word_level_embedding_layer == "True":
#             word_level_embedddings = self.word_level_embedddings(word_level_ids)
#         else:
#             word_level_embedddings = torch.zeros(size, device=self.position_ids.device)
#         if self.with_grammar_level_embedding_layer == "True":
#             grammar_level_embedddings = self.grammar_level_embedddings(grammar_level_ids)
#         else:
#             grammar_level_embedddings = torch.zeros(size, device=self.position_ids.device)
#
#         level_embeddings = character_level_embedddings + word_level_embedddings + grammar_level_embedddings
#         embeddings = inputs_embeds + level_embeddings + token_type_embeddings
#         if self.position_embedding_type == "absolute":
#             position_embeddings = self.position_embeddings(position_ids)
#             embeddings += position_embeddings
#         embeddings = self.LayerNorm(embeddings)
#         embeddings = self.dropout(embeddings)
#         return embeddings
#
# class BertSelfAttention(nn.Module):
#     def __init__(self, config, position_embedding_type=None):
#         super().__init__()
#         if config.hidden_size % config.num_attention_heads != 0 and not hasattr(config, "embedding_size"):
#             raise ValueError(
#                 f"The hidden size ({config.hidden_size}) is not a multiple of the number of attention "
#                 f"heads ({config.num_attention_heads})"
#             )
#
#         self.num_attention_heads = config.num_attention_heads  # 12
#         self.attention_head_size = int(config.hidden_size / config.num_attention_heads)  # 768 / 12 = 64
#         self.all_head_size = self.num_attention_heads * self.attention_head_size  # 12 * 64 = 768
#
#         self.query = nn.Linear(config.hidden_size, self.all_head_size)
#         self.key = nn.Linear(config.hidden_size, self.all_head_size)
#         self.value = nn.Linear(config.hidden_size, self.all_head_size)
#
#         self.dropout = nn.Dropout(config.attention_probs_dropout_prob)
#         self.position_embedding_type = position_embedding_type or getattr(
#             config, "position_embedding_type", "absolute"
#         )
#         if self.position_embedding_type == "relative_key" or self.position_embedding_type == "relative_key_query":
#             self.max_position_embeddings = config.max_position_embeddings
#             self.distance_embedding = nn.Embedding(2 * config.max_position_embeddings - 1, self.attention_head_size)
#
#         self.is_decoder = config.is_decoder
#
#     def transpose_for_scores(self, x):
#         new_x_shape = x.size()[:-1] + (self.num_attention_heads, self.attention_head_size)
#         x = x.view(*new_x_shape)
#         return x.permute(0, 2, 1, 3)
#
#     def forward(
#         self,
#         hidden_states,
#         attention_mask=None,
#         head_mask=None,
#         encoder_hidden_states=None,
#         encoder_attention_mask=None,
#         past_key_value=None,
#         output_attentions=False,
#     ):
#         mixed_query_layer = self.query(hidden_states)  # B x S x (H*d)
#
#         # If this is instantiated as a cross-attention module, the keys
#         # and values come from an encoder; the attention mask needs to be
#         # such that the encoder's padding tokens are not attended to.
#         is_cross_attention = encoder_hidden_states is not None
#
#         if is_cross_attention and past_key_value is not None:
#             # reuse k,v, cross_attentions
#             key_layer = past_key_value[0]
#             value_layer = past_key_value[1]
#             attention_mask = encoder_attention_mask
#         elif is_cross_attention:
#             key_layer = self.transpose_for_scores(self.key(encoder_hidden_states))
#             value_layer = self.transpose_for_scores(self.value(encoder_hidden_states))
#             attention_mask = encoder_attention_mask
#         elif past_key_value is not None:
#             key_layer = self.transpose_for_scores(self.key(hidden_states))
#             value_layer = self.transpose_for_scores(self.value(hidden_states))
#             key_layer = torch.cat([past_key_value[0], key_layer], dim=2)
#             value_layer = torch.cat([past_key_value[1], value_layer], dim=2)
#         else:
#             key_layer = self.transpose_for_scores(self.key(hidden_states))  # B x H x S x d
#             value_layer = self.transpose_for_scores(self.value(hidden_states))  # B x H x S x d
#
#         query_layer = self.transpose_for_scores(mixed_query_layer)  # B x H x S x d
#
#         if self.is_decoder:
#             # if cross_attention save Tuple(torch.Tensor, torch.Tensor) of all cross attention key/value_states.
#             # Further calls to cross_attention layer can then reuse all cross-attention
#             # key/value_states (first "if" case)
#             # if uni-directional self-attention (decoder) save Tuple(torch.Tensor, torch.Tensor) of
#             # all previous decoder key/value_states. Further calls to uni-directional self-attention
#             # can concat previous decoder key/value_states to current projected key/value_states (third "elif" case)
#             # if encoder bi-directional self-attention `past_key_value` is always `None`
#             past_key_value = (key_layer, value_layer)
#
#         # Take the dot product between "query" and "key" to get the raw attention scores.
#         attention_scores = torch.matmul(query_layer, key_layer.transpose(-1, -2))  # B x H x S x d · B x H x d x S -> B x H x S x S
#
#
#         if self.position_embedding_type == "relative_key" or self.position_embedding_type == "relative_key_query":
#             seq_length = hidden_states.size()[1]
#             position_ids_l = torch.arange(seq_length, dtype=torch.long, device=hidden_states.device).view(-1, 1)
#             position_ids_r = torch.arange(seq_length, dtype=torch.long, device=hidden_states.device).view(1, -1)
#             distance = position_ids_l - position_ids_r
#             positional_embedding = self.distance_embedding(distance + self.max_position_embeddings - 1)
#             positional_embedding = positional_embedding.to(dtype=query_layer.dtype)  # fp16 compatibility
#
#             if self.position_embedding_type == "relative_key":
#                 relative_position_scores = torch.einsum("bhld,lrd->bhlr", query_layer, positional_embedding)
#                 attention_scores = attention_scores + relative_position_scores
#             elif self.position_embedding_type == "relative_key_query":
#                 relative_position_scores_query = torch.einsum("bhld,lrd->bhlr", query_layer, positional_embedding)
#                 relative_position_scores_key = torch.einsum("bhrd,lrd->bhlr", key_layer, positional_embedding)
#                 attention_scores = attention_scores + relative_position_scores_query + relative_position_scores_key
#
#         attention_scores = attention_scores / math.sqrt(self.attention_head_size)  # B x H x S x S
#         if attention_mask is not None:
#             # Apply the attention mask is (precomputed for all layers in BertModel forward() function)
#             attention_scores = attention_scores + attention_mask
#
#         # Normalize the attention scores to probabilities.
#         attention_probs = nn.functional.softmax(attention_scores, dim=-1)  # B x H x S x S
#
#         # This is actually dropping out entire tokens to attend to, which might
#         # seem a bit unusual, but is taken from the original Transformer paper.
#         attention_probs = self.dropout(attention_probs)  # B x H x S x S
#
#         # Mask heads if we want to
#         if head_mask is not None:
#             attention_probs = attention_probs * head_mask
#
#         context_layer = torch.matmul(attention_probs, value_layer)  # B x H x S x S · B x H x S x d ->  B x H x S x d
#
#         context_layer = context_layer.permute(0, 2, 1, 3).contiguous()  # B x S x H x d
#         new_context_layer_shape = context_layer.size()[:-2] + (self.all_head_size,)
#         context_layer = context_layer.view(*new_context_layer_shape)  # B x S x D
#
#         outputs = (context_layer, attention_probs) if output_attentions else (context_layer,)
#
#         if self.is_decoder:
#             outputs = outputs + (past_key_value,)
#         return outputs
#
# class BertSelfAttention_ling(nn.Module):
#     def __init__(self, config, position_embedding_type=None):
#         super().__init__()
#         if config.hidden_size % config.num_attention_heads != 0 and not hasattr(config, "embedding_size"):
#             raise ValueError(
#                 f"The hidden size ({config.hidden_size}) is not a multiple of the number of attention "
#                 f"heads ({config.num_attention_heads})"
#             )
#         self.num_attention_heads = config.num_attention_heads  # 12
#         self.attention_head_size = int(config.hidden_size / config.num_attention_heads)  # 768 / 12 = 64
#         self.all_head_size = self.num_attention_heads * self.attention_head_size  # 12 * 64 = 768
#
#         self.query = nn.Linear(config.hidden_size, self.all_head_size)
#         self.key = nn.Linear(config.hidden_size, self.all_head_size)
#         self.value = nn.Linear(config.hidden_size, self.all_head_size)
#
#         self.dropout = nn.Dropout(config.attention_probs_dropout_prob)
#         self.position_embedding_type = position_embedding_type or getattr(
#             config, "position_embedding_type", "absolute"
#         )
#         if self.position_embedding_type == "relative_key" or self.position_embedding_type == "relative_key_query":
#             self.max_position_embeddings = config.max_position_embeddings
#             self.distance_embedding = nn.Embedding(2 * config.max_position_embeddings - 1, self.attention_head_size)
#
#         self.is_decoder = config.is_decoder
#
#         self.with_character_level_selfattention_layer = config.with_character_level_selfattention_layer
#         self.with_word_level_selfattention_layer = config.with_word_level_selfattention_layer
#         self.with_grammar_level_selfattention_layer = config.with_grammar_level_selfattention_layer
#
#         self.character_level_hp_selfattention_layer = config.character_level_hp_selfattention_layer
#         self.word_level_hp_selfattention_layer = config.word_level_hp_selfattention_layer
#         self.grammar_level_hp_selfattention_layer = config.grammar_level_hp_selfattention_layer
#
#         if self.with_character_level_selfattention_layer == 'True':
#             print('add character_level_layer')
#         if self.with_word_level_selfattention_layer == 'True':
#             print('add word_level_layer')
#         if self.with_grammar_level_selfattention_layer == 'True':
#             print('add grammar_level_layer')
#
#         # 是否使用nnembedding处理等级矩阵
#         self.level_with_nnembedding = config.level_with_nnembedding
#         if self.level_with_nnembedding == 'True':
#             self.character_level_nnembedding = nn.Embedding(8, 1)
#             self.word_level_nnembedding = nn.Embedding(8, 1)
#             self.grammar_level_nnembedding = nn.Embedding(8, 1)
#
#     def transpose_for_scores(self, x):
#         new_x_shape = x.size()[:-1] + (self.num_attention_heads, self.attention_head_size)
#         x = x.view(*new_x_shape)
#         return x.permute(0, 2, 1, 3)
#
#     def level_matrix_repeat(self, x):
#         return x.unsqueeze(1).repeat(1, self.num_attention_heads, 1, 1)
#
#     def forward(
#         self,
#         hidden_states,
#         attention_mask=None,
#         head_mask=None,
#         encoder_hidden_states=None,
#         encoder_attention_mask=None,
#         past_key_value=None,
#         output_attentions=False,
#         character_level_matrix=None,
#         word_level_matrix=None,
#         grammar_level_matrix=None,
#     ):
#         if self.level_with_nnembedding == 'True':
#             character_level_matrix = self.character_level_nnembedding(character_level_matrix.long())  # B x S x S -> B x S x S x 1
#             character_level_matrix = character_level_matrix.squeeze(-1)    # B x S x S x 1 -> B x S x S
#             word_level_matrix = self.word_level_nnembedding(word_level_matrix.long())  # B x S x S -> B x S x S x 1
#             word_level_matrix = word_level_matrix.squeeze(-1)  # B x S x S x 1 -> B x S x S
#             grammar_level_matrix = self.grammar_level_nnembedding(grammar_level_matrix.long())  # B x S x S -> B x S x S x 1
#             grammar_level_matrix = grammar_level_matrix.squeeze(-1)  # B x S x S x 1 -> B x S x S
#
#
#         if self.with_character_level_selfattention_layer == 'True':
#             character_level_layer = self.level_matrix_repeat(character_level_matrix)  # B x S x S -> B x H x S x S
#         if self.with_word_level_selfattention_layer == 'True':
#             word_level_layer = self.level_matrix_repeat(word_level_matrix)  # B x S x S -> B x H x S x S
#         if self.with_grammar_level_selfattention_layer == 'True':
#             grammar_level_layer = self.level_matrix_repeat(grammar_level_matrix)  # B x S x S -> B x H x S x S
#
#         mixed_query_layer = self.query(hidden_states)  # B x S x (H*d)
#
#         # If this is instantiated as a cross-attention module, the keys
#         # and values come from an encoder; the attention mask needs to be
#         # such that the encoder's padding tokens are not attended to.
#         is_cross_attention = encoder_hidden_states is not None
#
#         if is_cross_attention and past_key_value is not None:
#             # reuse k,v, cross_attentions
#             key_layer = past_key_value[0]
#             value_layer = past_key_value[1]
#             attention_mask = encoder_attention_mask
#         elif is_cross_attention:
#             key_layer = self.transpose_for_scores(self.key(encoder_hidden_states))
#             value_layer = self.transpose_for_scores(self.value(encoder_hidden_states))
#             attention_mask = encoder_attention_mask
#         elif past_key_value is not None:
#             key_layer = self.transpose_for_scores(self.key(hidden_states))
#             value_layer = self.transpose_for_scores(self.value(hidden_states))
#             key_layer = torch.cat([past_key_value[0], key_layer], dim=2)
#             value_layer = torch.cat([past_key_value[1], value_layer], dim=2)
#         else:
#             key_layer = self.transpose_for_scores(self.key(hidden_states))  # B x H x S x d
#             value_layer = self.transpose_for_scores(self.value(hidden_states))  # B x H x S x d
#
#         query_layer = self.transpose_for_scores(mixed_query_layer)  # B x H x S x d
#
#         if self.is_decoder:
#             # if cross_attention save Tuple(torch.Tensor, torch.Tensor) of all cross attention key/value_states.
#             # Further calls to cross_attention layer can then reuse all cross-attention
#             # key/value_states (first "if" case)
#             # if uni-directional self-attention (decoder) save Tuple(torch.Tensor, torch.Tensor) of
#             # all previous decoder key/value_states. Further calls to uni-directional self-attention
#             # can concat previous decoder key/value_states to current projected key/value_states (third "elif" case)
#             # if encoder bi-directional self-attention `past_key_value` is always `None`
#             past_key_value = (key_layer, value_layer)
#
#         # Take the dot product between "query" and "key" to get the raw attention scores.
#         attention_scores = torch.matmul(query_layer, key_layer.transpose(-1, -2))  # B x H x S x d · B x H x d x S -> B x H x S x S
#
#         # 添加等级矩阵到attention_scores
#         if self.with_character_level_selfattention_layer == 'True':
#             attention_scores += self.character_level_hp_selfattention_layer * character_level_layer
#         if self.with_word_level_selfattention_layer == 'True':
#             attention_scores += self.word_level_hp_selfattention_layer * word_level_layer
#         if self.with_grammar_level_selfattention_layer == 'True':
#             attention_scores += self.grammar_level_hp_selfattention_layer * grammar_level_layer
#
#         if self.position_embedding_type == "relative_key" or self.position_embedding_type == "relative_key_query":
#             seq_length = hidden_states.size()[1]
#             position_ids_l = torch.arange(seq_length, dtype=torch.long, device=hidden_states.device).view(-1, 1)
#             position_ids_r = torch.arange(seq_length, dtype=torch.long, device=hidden_states.device).view(1, -1)
#             distance = position_ids_l - position_ids_r
#             positional_embedding = self.distance_embedding(distance + self.max_position_embeddings - 1)
#             positional_embedding = positional_embedding.to(dtype=query_layer.dtype)  # fp16 compatibility
#
#             if self.position_embedding_type == "relative_key":
#                 relative_position_scores = torch.einsum("bhld,lrd->bhlr", query_layer, positional_embedding)
#                 attention_scores = attention_scores + relative_position_scores
#             elif self.position_embedding_type == "relative_key_query":
#                 relative_position_scores_query = torch.einsum("bhld,lrd->bhlr", query_layer, positional_embedding)
#                 relative_position_scores_key = torch.einsum("bhrd,lrd->bhlr", key_layer, positional_embedding)
#                 attention_scores = attention_scores + relative_position_scores_query + relative_position_scores_key
#
#         attention_scores = attention_scores / math.sqrt(self.attention_head_size)  # B x H x S x S
#         if attention_mask is not None:
#             # Apply the attention mask is (precomputed for all layers in BertModel forward() function)
#             attention_scores = attention_scores + attention_mask
#
#         # Normalize the attention scores to probabilities.
#         attention_probs = nn.functional.softmax(attention_scores, dim=-1)  # B x H x S x S
#
#         # This is actually dropping out entire tokens to attend to, which might
#         # seem a bit unusual, but is taken from the original Transformer paper.
#         attention_probs = self.dropout(attention_probs)  # B x H x S x S
#
#         # Mask heads if we want to
#         if head_mask is not None:
#             attention_probs = attention_probs * head_mask
#
#         context_layer = torch.matmul(attention_probs, value_layer)  # B x H x S x S · B x H x S x d ->  B x H x S x d
#
#         context_layer = context_layer.permute(0, 2, 1, 3).contiguous()  # B x S x H x d
#         new_context_layer_shape = context_layer.size()[:-2] + (self.all_head_size,)
#         context_layer = context_layer.view(*new_context_layer_shape)  # B x S x D
#
#         outputs = (context_layer, attention_probs) if output_attentions else (context_layer,)
#
#         if self.is_decoder:
#             outputs = outputs + (past_key_value,)
#         return outputs
#
# class BertSelfOutput(nn.Module):
#     def __init__(self, config):
#         super().__init__()
#         self.dense = nn.Linear(config.hidden_size, config.hidden_size)
#         self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
#         self.dropout = nn.Dropout(config.hidden_dropout_prob)
#
#     def forward(self, hidden_states, input_tensor):
#         hidden_states = self.dense(hidden_states)
#         hidden_states = self.dropout(hidden_states)
#         hidden_states = self.LayerNorm(hidden_states + input_tensor)
#         return hidden_states
#
# class BertAttention(nn.Module):
#     def __init__(self, config, position_embedding_type=None, with_ling=False):
#         super().__init__()
#         if with_ling == True:
#             self.with_ling = True
#             self.self = BertSelfAttention_ling(config, position_embedding_type=position_embedding_type)
#         else:
#             self.with_ling = False
#             self.self = BertSelfAttention(config, position_embedding_type=position_embedding_type)
#         self.output = BertSelfOutput(config)
#         self.pruned_heads = set()
#
#     def prune_heads(self, heads):
#         if len(heads) == 0:
#             return
#         heads, index = find_pruneable_heads_and_indices(
#             heads, self.self.num_attention_heads, self.self.attention_head_size, self.pruned_heads
#         )
#
#         # Prune linear layers
#         self.self.query = prune_linear_layer(self.self.query, index)
#         self.self.key = prune_linear_layer(self.self.key, index)
#         self.self.value = prune_linear_layer(self.self.value, index)
#         self.output.dense = prune_linear_layer(self.output.dense, index, dim=1)
#
#         # Update hyper params and store pruned heads
#         self.self.num_attention_heads = self.self.num_attention_heads - len(heads)
#         self.self.all_head_size = self.self.attention_head_size * self.self.num_attention_heads
#         self.pruned_heads = self.pruned_heads.union(heads)
#
#     def forward(
#         self,
#         hidden_states,
#         attention_mask=None,
#         head_mask=None,
#         encoder_hidden_states=None,
#         encoder_attention_mask=None,
#         past_key_value=None,
#         output_attentions=False,
#         character_level_matrix=None,
#         word_level_matrix=None,
#         grammar_level_matrix=None,
#     ):
#         if self.with_ling == True:
#             self_outputs = self.self(
#                 hidden_states,
#                 attention_mask,
#                 head_mask,
#                 encoder_hidden_states,
#                 encoder_attention_mask,
#                 past_key_value,
#                 output_attentions,
#                 character_level_matrix=character_level_matrix,
#                 word_level_matrix=word_level_matrix,
#                 grammar_level_matrix=grammar_level_matrix
#             )
#         else:
#             self_outputs = self.self(
#                 hidden_states,
#                 attention_mask,
#                 head_mask,
#                 encoder_hidden_states,
#                 encoder_attention_mask,
#                 past_key_value,
#                 output_attentions,
#             )
#         attention_output = self.output(self_outputs[0], hidden_states)
#         outputs = (attention_output,) + self_outputs[1:]  # add attentions if we output them
#         return outputs
#
# class BertIntermediate(nn.Module):
#     def __init__(self, config):
#         super().__init__()
#         self.dense = nn.Linear(config.hidden_size, config.intermediate_size)
#         if isinstance(config.hidden_act, str):
#             self.intermediate_act_fn = ACT2FN[config.hidden_act]
#         else:
#             self.intermediate_act_fn = config.hidden_act
#
#     def forward(self, hidden_states):
#         hidden_states = self.dense(hidden_states)
#         hidden_states = self.intermediate_act_fn(hidden_states)
#         return hidden_states
#
# class BertOutput(nn.Module):
#     def __init__(self, config):
#         super().__init__()
#         self.dense = nn.Linear(config.intermediate_size, config.hidden_size)
#         self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
#         self.dropout = nn.Dropout(config.hidden_dropout_prob)
#
#     def forward(self, hidden_states, input_tensor):
#         hidden_states = self.dense(hidden_states)
#         hidden_states = self.dropout(hidden_states)
#         hidden_states = self.LayerNorm(hidden_states + input_tensor)
#         return hidden_states
#
# class BertLayer(nn.Module):
#     def __init__(self, config, with_ling=False):
#         super().__init__()
#         self.chunk_size_feed_forward = config.chunk_size_feed_forward
#         self.seq_len_dim = 1
#         if with_ling == True:
#             self.with_ling = True
#             self.attention = BertAttention(config, with_ling=True)
#         else:
#             self.with_ling = False
#             self.attention = BertAttention(config)
#         self.is_decoder = config.is_decoder
#         self.add_cross_attention = config.add_cross_attention
#         if self.add_cross_attention:
#             if not self.is_decoder:
#                 raise ValueError(f"{self} should be used as a decoder model if cross attention is added")
#             self.crossattention = BertAttention(config, position_embedding_type="absolute")
#         self.intermediate = BertIntermediate(config)
#         self.output = BertOutput(config)
#
#     def forward(
#         self,
#         hidden_states,
#         attention_mask=None,
#         head_mask=None,
#         encoder_hidden_states=None,
#         encoder_attention_mask=None,
#         past_key_value=None,
#         output_attentions=False,
#         character_level_matrix=None,
#         word_level_matrix=None,
#         grammar_level_matrix=None,
#     ):
#         # decoder uni-directional self-attention cached key/values tuple is at positions 1,2
#         self_attn_past_key_value = past_key_value[:2] if past_key_value is not None else None
#         if self.with_ling == True:
#             self_attention_outputs = self.attention(
#                 hidden_states,
#                 attention_mask,
#                 head_mask,
#                 output_attentions=output_attentions,
#                 past_key_value=self_attn_past_key_value,
#                 character_level_matrix=character_level_matrix,
#                 word_level_matrix=word_level_matrix,
#                 grammar_level_matrix=grammar_level_matrix
#             )
#         else:
#             self_attention_outputs = self.attention(
#                 hidden_states,
#                 attention_mask,
#                 head_mask,
#                 output_attentions=output_attentions,
#                 past_key_value=self_attn_past_key_value,
#             )
#         attention_output = self_attention_outputs[0]
#
#         # if decoder, the last output is tuple of self-attn cache
#         if self.is_decoder:
#             outputs = self_attention_outputs[1:-1]
#             present_key_value = self_attention_outputs[-1]
#         else:
#             outputs = self_attention_outputs[1:]  # add self attentions if we output attention weights
#
#         cross_attn_present_key_value = None
#         if self.is_decoder and encoder_hidden_states is not None:
#             if not hasattr(self, "crossattention"):
#                 raise ValueError(
#                     f"If `encoder_hidden_states` are passed, {self} has to be instantiated with cross-attention layers by setting `config.add_cross_attention=True`"
#                 )
#
#             # cross_attn cached key/values tuple is at positions 3,4 of past_key_value tuple
#             cross_attn_past_key_value = past_key_value[-2:] if past_key_value is not None else None
#             cross_attention_outputs = self.crossattention(
#                 attention_output,
#                 attention_mask,
#                 head_mask,
#                 encoder_hidden_states,
#                 encoder_attention_mask,
#                 cross_attn_past_key_value,
#                 output_attentions,
#             )
#             attention_output = cross_attention_outputs[0]
#             outputs = outputs + cross_attention_outputs[1:-1]  # add cross attentions if we output attention weights
#
#             # add cross-attn cache to positions 3,4 of present_key_value tuple
#             cross_attn_present_key_value = cross_attention_outputs[-1]
#             present_key_value = present_key_value + cross_attn_present_key_value
#
#         layer_output = apply_chunking_to_forward(
#             self.feed_forward_chunk, self.chunk_size_feed_forward, self.seq_len_dim, attention_output
#         )
#         outputs = (layer_output,) + outputs
#
#         # if decoder, return the attn key/values as the last output
#         if self.is_decoder:
#             outputs = outputs + (present_key_value,)
#
#         return outputs
#
#     def feed_forward_chunk(self, attention_output):
#         intermediate_output = self.intermediate(attention_output)
#         layer_output = self.output(intermediate_output, attention_output)
#         return layer_output
#
# class BertEncoder(nn.Module):
#     def __init__(self, config):
#         super().__init__()
#         self.config = config
#         self.linguistic_information_selfattention_layer_num = config.linguistic_information_selfattention_layer_num
#         self.add_begin_attention_layer = config.add_begin_attention_layer
#         self.with_linguistic_information_selfattention_layer = config.with_linguistic_information_selfattention_layer
#         # print('with_linguistic_information_selfattention_layer = ' + str(self.with_linguistic_information_selfattention_layer))
#
#
#         if self.with_linguistic_information_selfattention_layer == 'False':
#             print(('---Using BertSelfAttention---'))
#             self.linguistic_information_selfattention_layer_num = 0
#         else:
#             print(('---Using BertSelfAttention_ling---'))
#         print('linguistic_information_selfattention_layer_num = ' + str(self.linguistic_information_selfattention_layer_num))
#         print('add_begin_attention_layer = ' + str(self.add_begin_attention_layer))
#
#         self.layer = nn.ModuleList(
#             [BertLayer(config) for _ in range(self.add_begin_attention_layer)] +
#             [BertLayer(config, with_ling=True) for _ in range(self.linguistic_information_selfattention_layer_num)] +
#             [BertLayer(config) for _ in range(config.num_hidden_layers - self.linguistic_information_selfattention_layer_num - self.add_begin_attention_layer)])
#         self.gradient_checkpointing = False
#
#     def forward(
#         self,
#         hidden_states,
#         attention_mask=None,
#         head_mask=None,
#         encoder_hidden_states=None,
#         encoder_attention_mask=None,
#         past_key_values=None,
#         use_cache=None,
#         output_attentions=False,
#         output_hidden_states=False,
#         return_dict=True,
#         character_level_matrix=None,
#         word_level_matrix=None,
#         grammar_level_matrix=None,
#     ):
#         all_hidden_states = () if output_hidden_states else None
#         all_self_attentions = () if output_attentions else None
#         all_cross_attentions = () if output_attentions and self.config.add_cross_attention else None
#
#         next_decoder_cache = () if use_cache else None
#
#         for i, layer_module in enumerate(self.layer):
#             if output_hidden_states:
#                 all_hidden_states = all_hidden_states + (hidden_states,)
#
#             layer_head_mask = head_mask[i] if head_mask is not None else None
#             past_key_value = past_key_values[i] if past_key_values is not None else None
#
#             if self.gradient_checkpointing and self.training:
#
#                 if use_cache:
#                     logger.warning(
#                         "`use_cache=True` is incompatible with gradient checkpointing. Setting `use_cache=False`..."
#                     )
#                     use_cache = False
#
#                 def create_custom_forward(module):
#                     def custom_forward(*inputs):
#                         return module(*inputs, past_key_value, output_attentions)
#
#                     return custom_forward
#                 if i < self.linguistic_information_selfattention_layer_num:
#                     layer_outputs = torch.utils.checkpoint.checkpoint(
#                         create_custom_forward(layer_module),
#                         hidden_states,
#                         attention_mask,
#                         layer_head_mask,
#                         encoder_hidden_states,
#                         encoder_attention_mask,
#                         character_level_matrix=character_level_matrix,
#                         word_level_matrix=word_level_matrix,
#                         grammar_level_matrix=grammar_level_matrix,
#                     )
#                 else:
#                     layer_outputs = torch.utils.checkpoint.checkpoint(
#                         create_custom_forward(layer_module),
#                         hidden_states,
#                         attention_mask,
#                         layer_head_mask,
#                         encoder_hidden_states,
#                         encoder_attention_mask,
#                     )
#             else:
#                 if self.add_begin_attention_layer <= i < self.linguistic_information_selfattention_layer_num + self.add_begin_attention_layer:
#                     layer_outputs = layer_module(
#                         hidden_states,
#                         attention_mask,
#                         layer_head_mask,
#                         encoder_hidden_states,
#                         encoder_attention_mask,
#                         past_key_value,
#                         output_attentions,
#                         character_level_matrix=character_level_matrix,
#                         word_level_matrix=word_level_matrix,
#                         grammar_level_matrix=grammar_level_matrix,
#                     )
#                 else:
#                     layer_outputs = layer_module(
#                         hidden_states,
#                         attention_mask,
#                         layer_head_mask,
#                         encoder_hidden_states,
#                         encoder_attention_mask,
#                         past_key_value,
#                         output_attentions,
#                     )
#
#             hidden_states = layer_outputs[0]
#             if use_cache:
#                 next_decoder_cache += (layer_outputs[-1],)
#             if output_attentions:
#                 all_self_attentions = all_self_attentions + (layer_outputs[1],)
#                 if self.config.add_cross_attention:
#                     all_cross_attentions = all_cross_attentions + (layer_outputs[2],)
#
#         if output_hidden_states:
#             all_hidden_states = all_hidden_states + (hidden_states,)
#
#         if not return_dict:
#             return tuple(
#                 v
#                 for v in [
#                     hidden_states,
#                     next_decoder_cache,
#                     all_hidden_states,
#                     all_self_attentions,
#                     all_cross_attentions,
#                 ]
#                 if v is not None
#             )
#         return BaseModelOutputWithPastAndCrossAttentions(
#             last_hidden_state=hidden_states,
#             past_key_values=next_decoder_cache,
#             hidden_states=all_hidden_states,
#             attentions=all_self_attentions,
#             cross_attentions=all_cross_attentions,
#         )
#
# class BertPooler(nn.Module):
#     def __init__(self, config):
#         super().__init__()
#         self.dense = nn.Linear(config.hidden_size, config.hidden_size)
#         self.activation = nn.Tanh()
#
#     def forward(self, hidden_states):
#         # We "pool" the model by simply taking the hidden state corresponding
#         # to the first token.
#         first_token_tensor = hidden_states[:, 0]
#         pooled_output = self.dense(first_token_tensor)
#         pooled_output = self.activation(pooled_output)
#         return pooled_output
#
# class BertModel(BertPreTrainedModel):
#     def __init__(self, config, add_pooling_layer=True):
#         super().__init__(config)
#         self.config = config
#
#         if self.config.with_linguistic_information_embedding_layer == 'False':
#             print('---Using BertEmbeddings---')
#             self.embeddings = BertEmbeddings(config)
#         else:
#             print('---Using BertEmbeddings_ling---')
#             self.embeddings = BertEmbeddings_ling(config)
#
#         self.encoder = BertEncoder(config)
#
#         self.pooler = BertPooler(config) if add_pooling_layer else None
#         #
#         # # Initialize weights and apply final processing
#         # self.post_init()
#
#     def get_input_embeddings(self):
#         return self.embeddings.word_embeddings
#
#     def set_input_embeddings(self, value):
#         self.embeddings.word_embeddings = value
#
#     def _prune_heads(self, heads_to_prune):
#         """
#         Prunes heads of the model. heads_to_prune: dict of {layer_num: list of heads to prune in this layer} See base
#         class PreTrainedModel
#         """
#         for layer, heads in heads_to_prune.items():
#             self.encoder.layer[layer].attention.prune_heads(heads)
#
#     # @add_start_docstrings_to_model_forward(BERT_INPUTS_DOCSTRING.format("batch_size, sequence_length"))
#     # @add_code_sample_docstrings(
#     #     processor_class=_TOKENIZER_FOR_DOC,
#     #     checkpoint=_CHECKPOINT_FOR_DOC,
#     #     output_type=BaseModelOutputWithPoolingAndCrossAttentions,
#     #     config_class=_CONFIG_FOR_DOC,
#     # )
#     def forward(
#         self,
#         input_ids=None,
#         attention_mask=None,
#         token_type_ids=None,
#         position_ids=None,
#         head_mask=None,
#         inputs_embeds=None,
#         encoder_hidden_states=None,
#         encoder_attention_mask=None,
#         past_key_values=None,
#         use_cache=None,
#         output_attentions=None,
#         output_hidden_states=None,
#         return_dict=None,
#         character_level_ids=None,
#         word_level_ids=None,
#         grammar_level_ids=None,
#         character_level_matrix=None,
#         word_level_matrix=None,
#         grammar_level_matrix=None
#     ):
#         r"""
#         encoder_hidden_states  (:obj:`torch.FloatTensor` of shape :obj:`(batch_size, sequence_length, hidden_size)`, `optional`):
#             Sequence of hidden-states at the output of the last layer of the encoder. Used in the cross-attention if
#             the model is configured as a decoder.
#         encoder_attention_mask (:obj:`torch.FloatTensor` of shape :obj:`(batch_size, sequence_length)`, `optional`):
#             Mask to avoid performing attention on the padding token indices of the encoder input. This mask is used in
#             the cross-attention if the model is configured as a decoder. Mask values selected in ``[0, 1]``:
#
#             - 1 for tokens that are **not masked**,
#             - 0 for tokens that are **masked**.
#         past_key_values (:obj:`tuple(tuple(torch.FloatTensor))` of length :obj:`config.n_layers` with each tuple having 4 tensors of shape :obj:`(batch_size, num_heads, sequence_length - 1, embed_size_per_head)`):
#             Contains precomputed key and value hidden states of the attention blocks. Can be used to speed up decoding.
#
#             If :obj:`past_key_values` are used, the user can optionally input only the last :obj:`decoder_input_ids`
#             (those that don't have their past key value states given to this model) of shape :obj:`(batch_size, 1)`
#             instead of all :obj:`decoder_input_ids` of shape :obj:`(batch_size, sequence_length)`.
#         use_cache (:obj:`bool`, `optional`):
#             If set to :obj:`True`, :obj:`past_key_values` key value states are returned and can be used to speed up
#             decoding (see :obj:`past_key_values`).
#         """
#         output_attentions = output_attentions if output_attentions is not None else self.config.output_attentions
#
#         output_hidden_states = (
#             output_hidden_states if output_hidden_states is not None else self.config.output_hidden_states
#         )
#         return_dict = return_dict if return_dict is not None else self.config.use_return_dict
#
#         if self.config.is_decoder:
#             use_cache = use_cache if use_cache is not None else self.config.use_cache
#         else:
#             use_cache = False
#
#         if input_ids is not None and inputs_embeds is not None:
#             raise ValueError("You cannot specify both input_ids and inputs_embeds at the same time")
#         elif input_ids is not None:
#             input_shape = input_ids.size()
#         elif inputs_embeds is not None:
#             input_shape = inputs_embeds.size()[:-1]
#         else:
#             raise ValueError("You have to specify either input_ids or inputs_embeds")
#
#         batch_size, seq_length = input_shape
#         device = input_ids.device if input_ids is not None else inputs_embeds.device
#
#         # past_key_values_length
#         past_key_values_length = past_key_values[0][0].shape[2] if past_key_values is not None else 0
#
#         if attention_mask is None:
#             attention_mask = torch.ones(((batch_size, seq_length + past_key_values_length)), device=device)
#
#         if token_type_ids is None:
#             if hasattr(self.embeddings, "token_type_ids"):
#                 buffered_token_type_ids = self.embeddings.token_type_ids[:, :seq_length]
#                 buffered_token_type_ids_expanded = buffered_token_type_ids.expand(batch_size, seq_length)
#                 token_type_ids = buffered_token_type_ids_expanded
#             else:
#                 token_type_ids = torch.zeros(input_shape, dtype=torch.long, device=device)
#
#         # We can provide a self-attention mask of dimensions [batch_size, from_seq_length, to_seq_length]
#         # ourselves in which case we just need to make it broadcastable to all heads.
#         extended_attention_mask: torch.Tensor = self.get_extended_attention_mask(attention_mask, input_shape, device)
#
#         # If a 2D or 3D attention mask is provided for the cross-attention
#         # we need to make broadcastable to [batch_size, num_heads, seq_length, seq_length]
#         if self.config.is_decoder and encoder_hidden_states is not None:
#             encoder_batch_size, encoder_sequence_length, _ = encoder_hidden_states.size()
#             encoder_hidden_shape = (encoder_batch_size, encoder_sequence_length)
#             if encoder_attention_mask is None:
#                 encoder_attention_mask = torch.ones(encoder_hidden_shape, device=device)
#             encoder_extended_attention_mask = self.invert_attention_mask(encoder_attention_mask)
#         else:
#             encoder_extended_attention_mask = None
#
#         # Prepare head mask if needed
#         # 1.0 in head_mask indicate we keep the head
#         # attention_probs has shape bsz x n_heads x N x N
#         # input head_mask has shape [num_heads] or [num_hidden_layers x num_heads]
#         # and head_mask is converted to shape [num_hidden_layers x batch x num_heads x seq_length x seq_length]
#         head_mask = self.get_head_mask(head_mask, self.config.num_hidden_layers)
#
#         embedding_output = self.embeddings(
#             input_ids=input_ids,
#             position_ids=position_ids,
#             token_type_ids=token_type_ids,
#             inputs_embeds=inputs_embeds,
#             past_key_values_length=past_key_values_length,
#             character_level_ids=character_level_ids,
#             word_level_ids=word_level_ids,
#             grammar_level_ids=grammar_level_ids
#         )
#         encoder_outputs = self.encoder(
#             embedding_output,
#             attention_mask=extended_attention_mask,
#             head_mask=head_mask,
#             encoder_hidden_states=encoder_hidden_states,
#             encoder_attention_mask=encoder_extended_attention_mask,
#             past_key_values=past_key_values,
#             use_cache=use_cache,
#             output_attentions=output_attentions,
#             output_hidden_states=output_hidden_states,
#             return_dict=return_dict,
#             character_level_matrix=character_level_matrix,
#             word_level_matrix=word_level_matrix,
#             grammar_level_matrix=grammar_level_matrix
#         )
#         sequence_output = encoder_outputs[0]
#         pooled_output = self.pooler(sequence_output) if self.pooler is not None else None
#
#         if not return_dict:
#             return (sequence_output, pooled_output) + encoder_outputs[1:]
#
#         return BaseModelOutputWithPoolingAndCrossAttentions(
#             last_hidden_state=sequence_output,
#             pooler_output=pooled_output,
#             past_key_values=encoder_outputs.past_key_values,
#             hidden_states=encoder_outputs.hidden_states,
#             attentions=encoder_outputs.attentions,
#             cross_attentions=encoder_outputs.cross_attentions,
#         )



class BertEmbeddings(nn.Module):
    """Construct the embeddings from word, position and token_type embeddings."""

    def __init__(self, config):
        super().__init__()
        self.word_embeddings = nn.Embedding(config.vocab_size, config.hidden_size, padding_idx=config.pad_token_id)
        self.position_embeddings = nn.Embedding(config.max_position_embeddings, config.hidden_size)
        self.token_type_embeddings = nn.Embedding(config.type_vocab_size, config.hidden_size)

        # self.LayerNorm is not snake-cased to stick with TensorFlow model variable name and be able to load
        # any TensorFlow checkpoint file
        self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        # position_ids (1, len position emb) is contiguous in memory and exported when serialized
        self.position_embedding_type = getattr(config, "position_embedding_type", "absolute")
        self.register_buffer("position_ids", torch.arange(config.max_position_embeddings).expand((1, -1)))
        if version.parse(torch.__version__) > version.parse("1.6.0"):
            self.register_buffer(
                "token_type_ids",
                torch.zeros(self.position_ids.size(), dtype=torch.long),
                persistent=False,
            )

    def forward(
            self, input_ids=None, token_type_ids=None, position_ids=None, inputs_embeds=None,
            past_key_values_length=0,
            character_level_ids=None, word_level_ids=None
    ):
        if input_ids is not None:
            input_shape = input_ids.size()
        else:
            input_shape = inputs_embeds.size()[:-1]

        seq_length = input_shape[1]

        if position_ids is None:
            position_ids = self.position_ids[:, past_key_values_length: seq_length + past_key_values_length]

        # Setting the token_type_ids to the registered buffer in constructor where it is all zeros, which usually occurs
        # when its auto-generated, registered buffer helps users when tracing the model without passing token_type_ids
        if token_type_ids is None:
            if hasattr(self, "token_type_ids"):
                buffered_token_type_ids = self.token_type_ids[:, :seq_length]
                buffered_token_type_ids_expanded = buffered_token_type_ids.expand(input_shape[0], seq_length)
                token_type_ids = buffered_token_type_ids_expanded
            else:
                token_type_ids = torch.zeros(input_shape, dtype=torch.long, device=self.position_ids.device)

        if inputs_embeds is None:
            inputs_embeds = self.word_embeddings(input_ids)
        token_type_embeddings = self.token_type_embeddings(token_type_ids)

        embeddings = inputs_embeds + token_type_embeddings
        if self.position_embedding_type == "absolute":
            position_embeddings = self.position_embeddings(position_ids)
            embeddings += position_embeddings
        embeddings = self.LayerNorm(embeddings)
        embeddings = self.dropout(embeddings)
        return embeddings


class BertEmbeddings_ling(nn.Module):
    '''
    For fusing the linguistic features in the Embedding Layer.
    '''

    def __init__(self, config):
        super().__init__()
        self.word_embeddings = nn.Embedding(config.vocab_size, config.hidden_size, padding_idx=config.pad_token_id)
        self.position_embeddings = nn.Embedding(config.max_position_embeddings, config.hidden_size)
        self.token_type_embeddings = nn.Embedding(config.type_vocab_size, config.hidden_size)
        self.hidden_size = config.hidden_size
        self.with_character_level_embedding_layer = config.with_character_level_embedding_layer
        self.with_word_level_embedding_layer = config.with_word_level_embedding_layer
        self.character_level_embedddings = nn.Embedding(config.character_level_size_embedding_layer,
                                                        config.hidden_size)
        self.word_level_embedddings = nn.Embedding(config.word_level_size_embedding_layer, config.hidden_size)
        print('with_character_level_embedding_layer: ' + str(self.with_character_level_embedding_layer))
        print('with_word_level_embedding_layer: ' + str(self.with_word_level_embedding_layer))

        # self.LayerNorm is not snake-cased to stick with TensorFlow model variable name and be able to load
        # any TensorFlow checkpoint file
        self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        # position_ids (1, len position emb) is contiguous in memory and exported when serialized
        self.position_embedding_type = getattr(config, "position_embedding_type", "absolute")
        self.register_buffer("position_ids", torch.arange(config.max_position_embeddings).expand((1, -1)))
        if version.parse(torch.__version__) > version.parse("1.6.0"):
            self.register_buffer(
                "token_type_ids",
                torch.zeros(self.position_ids.size(), dtype=torch.long),
                persistent=False,
            )

    def forward(
            self, input_ids=None, token_type_ids=None, position_ids=None, inputs_embeds=None,
            past_key_values_length=0,
            character_level_ids=None, word_level_ids=None
    ):
        if input_ids is not None:
            input_shape = input_ids.size()
        else:
            input_shape = inputs_embeds.size()[:-1]

        seq_length = input_shape[1]

        if position_ids is None:
            position_ids = self.position_ids[:, past_key_values_length: seq_length + past_key_values_length]

        if token_type_ids is None:
            if hasattr(self, "token_type_ids"):
                buffered_token_type_ids = self.token_type_ids[:, :seq_length]
                buffered_token_type_ids_expanded = buffered_token_type_ids.expand(input_shape[0], seq_length)
                token_type_ids = buffered_token_type_ids_expanded
            else:
                token_type_ids = torch.zeros(input_shape, dtype=torch.long, device=self.position_ids.device)

        if inputs_embeds is None:
            inputs_embeds = self.word_embeddings(input_ids)

        token_type_embeddings = self.token_type_embeddings(token_type_ids)

        size = (input_ids.shape[0], input_ids.shape[1], self.hidden_size)
        if self.with_character_level_embedding_layer == "True":
            character_level_embedddings = self.character_level_embedddings(character_level_ids)
        else:
            character_level_embedddings = torch.zeros(size, device=self.position_ids.device)
        if self.with_word_level_embedding_layer == "True":
            word_level_embedddings = self.word_level_embedddings(word_level_ids)
        else:
            word_level_embedddings = torch.zeros(size, device=self.position_ids.device)

        level_embeddings = character_level_embedddings + word_level_embedddings
        embeddings = inputs_embeds + level_embeddings + token_type_embeddings
        if self.position_embedding_type == "absolute":
            position_embeddings = self.position_embeddings(position_ids)
            embeddings += position_embeddings
        embeddings = self.LayerNorm(embeddings)
        embeddings = self.dropout(embeddings)
        return embeddings



class BertSelfAttention(nn.Module):
    def __init__(self, config, position_embedding_type=None):
        super().__init__()
        if config.hidden_size % config.num_attention_heads != 0 and not hasattr(config, "embedding_size"):
            raise ValueError(
                f"The hidden size ({config.hidden_size}) is not a multiple of the number of attention "
                f"heads ({config.num_attention_heads})"
            )

        self.num_attention_heads = config.num_attention_heads
        self.attention_head_size = int(config.hidden_size / config.num_attention_heads)
        self.all_head_size = self.num_attention_heads * self.attention_head_size

        self.query = nn.Linear(config.hidden_size, self.all_head_size)
        self.key = nn.Linear(config.hidden_size, self.all_head_size)
        self.value = nn.Linear(config.hidden_size, self.all_head_size)

        self.dropout = nn.Dropout(config.attention_probs_dropout_prob)
        self.position_embedding_type = position_embedding_type or getattr(
            config, "position_embedding_type", "absolute"
        )
        if self.position_embedding_type in ["relative_key", "relative_key_query"]:
            self.max_position_embeddings = config.max_position_embeddings
            self.distance_embedding = nn.Embedding(2 * config.max_position_embeddings - 1, self.attention_head_size)

        self.is_decoder = config.is_decoder

    def transpose_for_scores(self, x):
        new_x_shape = x.size()[:-1] + (self.num_attention_heads, self.attention_head_size)
        x = x.view(*new_x_shape)
        return x.permute(0, 2, 1, 3)

    def forward(
        self,
        hidden_states,
        attention_mask=None,
        head_mask=None,
        encoder_hidden_states=None,
        encoder_attention_mask=None,
        past_key_value=None,
        output_attentions=False,
    ):
        mixed_query_layer = self.query(hidden_states)

        is_cross_attention = encoder_hidden_states is not None

        if is_cross_attention and past_key_value is not None:
            key_layer = past_key_value[0]
            value_layer = past_key_value[1]
            attention_mask = encoder_attention_mask
        elif is_cross_attention:
            key_layer = self.transpose_for_scores(self.key(encoder_hidden_states))
            value_layer = self.transpose_for_scores(self.value(encoder_hidden_states))
            attention_mask = encoder_attention_mask
        elif past_key_value is not None:
            key_layer = self.transpose_for_scores(self.key(hidden_states))
            value_layer = self.transpose_for_scores(self.value(hidden_states))
            key_layer = torch.cat([past_key_value[0], key_layer], dim=2)
            value_layer = torch.cat([past_key_value[1], value_layer], dim=2)
        else:
            key_layer = self.transpose_for_scores(self.key(hidden_states))
            value_layer = self.transpose_for_scores(self.value(hidden_states))

        query_layer = self.transpose_for_scores(mixed_query_layer)

        if self.is_decoder:
            past_key_value = (key_layer, value_layer)

        attention_scores = torch.matmul(query_layer, key_layer.transpose(-1, -2))

        if self.position_embedding_type in ["relative_key", "relative_key_query"]:
            seq_length = hidden_states.size(1)
            position_ids_l = torch.arange(seq_length, dtype=torch.long, device=hidden_states.device).view(-1, 1)
            position_ids_r = torch.arange(seq_length, dtype=torch.long, device=hidden_states.device).view(1, -1)
            distance = position_ids_l - position_ids_r
            positional_embedding = self.distance_embedding(distance + self.max_position_embeddings - 1)
            positional_embedding = positional_embedding.to(dtype=query_layer.dtype)

            if self.position_embedding_type == "relative_key":
                relative_position_scores = torch.einsum("bhld,lrd->bhlr", query_layer, positional_embedding)
                attention_scores += relative_position_scores
            elif self.position_embedding_type == "relative_key_query":
                relative_position_scores_query = torch.einsum("bhld,lrd->bhlr", query_layer, positional_embedding)
                relative_position_scores_key = torch.einsum("bhrd,lrd->bhlr", key_layer, positional_embedding)
                attention_scores += relative_position_scores_query + relative_position_scores_key

        attention_scores = attention_scores / math.sqrt(self.attention_head_size)
        if attention_mask is not None:
            attention_scores += attention_mask

        attention_probs = nn.functional.softmax(attention_scores, dim=-1)
        attention_probs = self.dropout(attention_probs)

        if head_mask is not None:
            attention_probs *= head_mask

        context_layer = torch.matmul(attention_probs, value_layer)
        context_layer = context_layer.permute(0, 2, 1, 3).contiguous()
        new_context_layer_shape = context_layer.size()[:-2] + (self.all_head_size,)
        context_layer = context_layer.view(*new_context_layer_shape)

        outputs = (context_layer, attention_probs) if output_attentions else (context_layer,)

        if self.is_decoder:
            outputs += (past_key_value,)
        return outputs


class BertSelfAttention_ling(nn.Module):
    def __init__(self, config, position_embedding_type=None):
        super().__init__()
        if config.hidden_size % config.num_attention_heads != 0 and not hasattr(config, "embedding_size"):
            raise ValueError(
                f"The hidden size ({config.hidden_size}) is not a multiple of the number of attention "
                f"heads ({config.num_attention_heads})"
            )
        self.num_attention_heads = config.num_attention_heads
        self.attention_head_size = int(config.hidden_size / config.num_attention_heads)
        self.all_head_size = self.num_attention_heads * self.attention_head_size

        self.query = nn.Linear(config.hidden_size, self.all_head_size)
        self.key = nn.Linear(config.hidden_size, self.all_head_size)
        self.value = nn.Linear(config.hidden_size, self.all_head_size)

        self.dropout = nn.Dropout(config.attention_probs_dropout_prob)
        self.position_embedding_type = position_embedding_type or getattr(
            config, "position_embedding_type", "absolute"
        )
        if self.position_embedding_type in ["relative_key", "relative_key_query"]:
            self.max_position_embeddings = config.max_position_embeddings
            self.distance_embedding = nn.Embedding(2 * config.max_position_embeddings - 1, self.attention_head_size)

        self.is_decoder = config.is_decoder

        self.with_character_level_selfattention_layer = config.with_character_level_selfattention_layer
        self.with_word_level_selfattention_layer = config.with_word_level_selfattention_layer

        self.character_level_hp_selfattention_layer = config.character_level_hp_selfattention_layer
        self.word_level_hp_selfattention_layer = config.word_level_hp_selfattention_layer

        self.level_with_nnembedding = config.level_with_nnembedding
        if self.level_with_nnembedding == 'True':
            self.character_level_nnembedding = nn.Embedding(8, 1)
            self.word_level_nnembedding = nn.Embedding(8, 1)

    def transpose_for_scores(self, x):
        new_x_shape = x.size()[:-1] + (self.num_attention_heads, self.attention_head_size)
        x = x.view(*new_x_shape)
        return x.permute(0, 2, 1, 3)

    def level_matrix_repeat(self, x):
        return x.unsqueeze(1).repeat(1, self.num_attention_heads, 1, 1)

    def forward(
        self,
        hidden_states,
        attention_mask=None,
        head_mask=None,
        encoder_hidden_states=None,
        encoder_attention_mask=None,
        past_key_value=None,
        output_attentions=False,
        character_level_matrix=None,
        word_level_matrix=None,
    ):
        if self.level_with_nnembedding == 'True':
            character_level_matrix = self.character_level_nnembedding(character_level_matrix.long()).squeeze(-1)
            word_level_matrix = self.word_level_nnembedding(word_level_matrix.long()).squeeze(-1)

        if self.with_character_level_selfattention_layer == 'True':
            character_level_layer = self.level_matrix_repeat(character_level_matrix)
        if self.with_word_level_selfattention_layer == 'True':
            word_level_layer = self.level_matrix_repeat(word_level_matrix)

        mixed_query_layer = self.query(hidden_states)

        is_cross_attention = encoder_hidden_states is not None

        if is_cross_attention and past_key_value is not None:
            key_layer = past_key_value[0]
            value_layer = past_key_value[1]
            attention_mask = encoder_attention_mask
        elif is_cross_attention:
            key_layer = self.transpose_for_scores(self.key(encoder_hidden_states))
            value_layer = self.transpose_for_scores(self.value(encoder_hidden_states))
            attention_mask = encoder_attention_mask
        elif past_key_value is not None:
            key_layer = self.transpose_for_scores(self.key(hidden_states))
            value_layer = self.transpose_for_scores(self.value(hidden_states))
            key_layer = torch.cat([past_key_value[0], key_layer], dim=2)
            value_layer = torch.cat([past_key_value[1], value_layer], dim=2)
        else:
            key_layer = self.transpose_for_scores(self.key(hidden_states))
            value_layer = self.transpose_for_scores(self.value(hidden_states))

        query_layer = self.transpose_for_scores(mixed_query_layer)

        if self.is_decoder:
            past_key_value = (key_layer, value_layer)

        attention_scores = torch.matmul(query_layer, key_layer.transpose(-1, -2))

        if self.with_character_level_selfattention_layer == 'True':
            attention_scores += self.character_level_hp_selfattention_layer * character_level_layer
        if self.with_word_level_selfattention_layer == 'True':
            attention_scores += self.word_level_hp_selfattention_layer * word_level_layer

        if self.position_embedding_type in ["relative_key", "relative_key_query"]:
            seq_length = hidden_states.size(1)
            position_ids_l = torch.arange(seq_length, dtype=torch.long, device=hidden_states.device).view(-1, 1)
            position_ids_r = torch.arange(seq_length, dtype=torch.long, device=hidden_states.device).view(1, -1)
            distance = position_ids_l - position_ids_r
            positional_embedding = self.distance_embedding(distance + self.max_position_embeddings - 1)
            positional_embedding = positional_embedding.to(dtype=query_layer.dtype)

            if self.position_embedding_type == "relative_key":
                relative_position_scores = torch.einsum("bhld,lrd->bhlr", query_layer, positional_embedding)
                attention_scores += relative_position_scores
            elif self.position_embedding_type == "relative_key_query":
                relative_position_scores_query = torch.einsum("bhld,lrd->bhlr", query_layer, positional_embedding)
                relative_position_scores_key = torch.einsum("bhrd,lrd->bhlr", key_layer, positional_embedding)
                attention_scores += relative_position_scores_query + relative_position_scores_key

        attention_scores = attention_scores / math.sqrt(self.attention_head_size)
        if attention_mask is not None:
            attention_scores += attention_mask

        attention_probs = nn.functional.softmax(attention_scores, dim=-1)
        attention_probs = self.dropout(attention_probs)

        if head_mask is not None:
            attention_probs *= head_mask

        context_layer = torch.matmul(attention_probs, value_layer)
        context_layer = context_layer.permute(0, 2, 1, 3).contiguous()
        new_context_layer_shape = context_layer.size()[:-2] + (self.all_head_size,)
        context_layer = context_layer.view(*new_context_layer_shape)

        outputs = (context_layer, attention_probs) if output_attentions else (context_layer,)

        if self.is_decoder:
            outputs += (past_key_value,)
        return outputs


import torch
import torch.nn as nn

class BertSelfOutput(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)

    def forward(self, hidden_states, input_tensor):
        hidden_states = self.dense(hidden_states)
        hidden_states = self.dropout(hidden_states)
        hidden_states = self.LayerNorm(hidden_states + input_tensor)
        return hidden_states


class BertAttention(nn.Module):
    def __init__(self, config, position_embedding_type=None, with_ling=False):
        super().__init__()
        if with_ling:
            self.with_ling = True
            self.self = BertSelfAttention_ling(config, position_embedding_type=position_embedding_type)
        else:
            self.with_ling = False
            self.self = BertSelfAttention(config, position_embedding_type=position_embedding_type)
        self.output = BertSelfOutput(config)
        self.pruned_heads = set()

    def prune_heads(self, heads):
        if len(heads) == 0:
            return
        heads, index = find_pruneable_heads_and_indices(
            heads, self.self.num_attention_heads, self.self.attention_head_size, self.pruned_heads
        )

        self.self.query = prune_linear_layer(self.self.query, index)
        self.self.key = prune_linear_layer(self.self.key, index)
        self.self.value = prune_linear_layer(self.self.value, index)
        self.output.dense = prune_linear_layer(self.output.dense, index, dim=1)

        self.self.num_attention_heads -= len(heads)
        self.self.all_head_size = self.self.attention_head_size * self.self.num_attention_heads
        self.pruned_heads = self.pruned_heads.union(heads)

    def forward(
        self,
        hidden_states,
        attention_mask=None,
        head_mask=None,
        encoder_hidden_states=None,
        encoder_attention_mask=None,
        past_key_value=None,
        output_attentions=False,
        character_level_matrix=None,
        word_level_matrix=None,
    ):
        if self.with_ling:
            self_outputs = self.self(
                hidden_states,
                attention_mask,
                head_mask,
                encoder_hidden_states,
                encoder_attention_mask,
                past_key_value,
                output_attentions,
                character_level_matrix=character_level_matrix,
                word_level_matrix=word_level_matrix,
            )
        else:
            self_outputs = self.self(
                hidden_states,
                attention_mask,
                head_mask,
                encoder_hidden_states,
                encoder_attention_mask,
                past_key_value,
                output_attentions,
            )
        attention_output = self.output(self_outputs[0], hidden_states)
        outputs = (attention_output,) + self_outputs[1:]  # Add attentions if we output them
        return outputs


class BertIntermediate(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.intermediate_size)
        self.intermediate_act_fn = ACT2FN[config.hidden_act] if isinstance(config.hidden_act, str) else config.hidden_act

    def forward(self, hidden_states):
        hidden_states = self.dense(hidden_states)
        hidden_states = self.intermediate_act_fn(hidden_states)
        return hidden_states


class BertOutput(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.intermediate_size, config.hidden_size)
        self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)

    def forward(self, hidden_states, input_tensor):
        hidden_states = self.dense(hidden_states)
        hidden_states = self.dropout(hidden_states)
        hidden_states = self.LayerNorm(hidden_states + input_tensor)
        return hidden_states


class BertLayer(nn.Module):
    def __init__(self, config, with_ling=False):
        super().__init__()
        self.chunk_size_feed_forward = config.chunk_size_feed_forward
        self.seq_len_dim = 1
        if with_ling:
            self.with_ling = True
            self.attention = BertAttention(config, with_ling=True)
        else:
            self.with_ling = False
            self.attention = BertAttention(config)
        self.is_decoder = config.is_decoder
        self.add_cross_attention = config.add_cross_attention
        if self.add_cross_attention:
            if not self.is_decoder:
                raise ValueError(f"{self} should be used as a decoder model if cross attention is added")
            self.crossattention = BertAttention(config, position_embedding_type="absolute")
        self.intermediate = BertIntermediate(config)
        self.output = BertOutput(config)

    def forward(
        self,
        hidden_states,
        attention_mask=None,
        head_mask=None,
        encoder_hidden_states=None,
        encoder_attention_mask=None,
        past_key_value=None,
        output_attentions=False,
        character_level_matrix=None,
        word_level_matrix=None,
    ):
        self_attn_past_key_value = past_key_value[:2] if past_key_value is not None else None
        if self.with_ling:
            self_attention_outputs = self.attention(
                hidden_states,
                attention_mask,
                head_mask,
                output_attentions=output_attentions,
                past_key_value=self_attn_past_key_value,
                character_level_matrix=character_level_matrix,
                word_level_matrix=word_level_matrix,
            )
        else:
            self_attention_outputs = self.attention(
                hidden_states,
                attention_mask,
                head_mask,
                output_attentions=output_attentions,
                past_key_value=self_attn_past_key_value,
            )
        attention_output = self_attention_outputs[0]

        if self.is_decoder:
            outputs = self_attention_outputs[1:-1]
            present_key_value = self_attention_outputs[-1]
        else:
            outputs = self_attention_outputs[1:]  # Add self attentions if we output attention weights

        cross_attn_present_key_value = None
        if self.is_decoder and encoder_hidden_states is not None:
            if not hasattr(self, "crossattention"):
                raise ValueError(
                    f"If `encoder_hidden_states` are passed, {self} has to be instantiated with cross-attention layers by setting `config.add_cross_attention=True`"
                )
            cross_attn_past_key_value = past_key_value[-2:] if past_key_value is not None else None
            cross_attention_outputs = self.crossattention(
                attention_output,
                attention_mask,
                head_mask,
                encoder_hidden_states,
                encoder_attention_mask,
                cross_attn_past_key_value,
                output_attentions,
            )
            attention_output = cross_attention_outputs[0]
            outputs = outputs + cross_attention_outputs[1:-1]  # Add cross attentions if we output attention weights

            cross_attn_present_key_value = cross_attention_outputs[-1]
            present_key_value = present_key_value + cross_attn_present_key_value

        layer_output = apply_chunking_to_forward(
            self.feed_forward_chunk, self.chunk_size_feed_forward, self.seq_len_dim, attention_output
        )
        outputs = (layer_output,) + outputs

        if self.is_decoder:
            outputs = outputs + (present_key_value,)

        return outputs

    def feed_forward_chunk(self, attention_output):
        intermediate_output = self.intermediate(attention_output)
        layer_output = self.output(intermediate_output, attention_output)
        return layer_output



import torch
import torch.nn as nn
from transformers.models.bert.modeling_bert import (
    BertPreTrainedModel,
    BaseModelOutputWithPoolingAndCrossAttentions,
)


class BertEncoder(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.linguistic_information_selfattention_layer_num = config.linguistic_information_selfattention_layer_num
        self.add_begin_attention_layer = config.add_begin_attention_layer
        self.with_linguistic_information_selfattention_layer = config.with_linguistic_information_selfattention_layer

        if self.with_linguistic_information_selfattention_layer == "False":
            print("---Using BertSelfAttention---")
            self.linguistic_information_selfattention_layer_num = 0
        else:
            print("---Using BertSelfAttention_ling---")
        print("linguistic_information_selfattention_layer_num =", self.linguistic_information_selfattention_layer_num)
        print("add_begin_attention_layer =", self.add_begin_attention_layer)

        self.layer = nn.ModuleList(
            [BertLayer(config) for _ in range(self.add_begin_attention_layer)]
            + [BertLayer(config, with_ling=True) for _ in range(self.linguistic_information_selfattention_layer_num)]
            + [
                BertLayer(config)
                for _ in range(
                    config.num_hidden_layers
                    - self.linguistic_information_selfattention_layer_num
                    - self.add_begin_attention_layer
                )
            ]
        )
        self.gradient_checkpointing = False

    def forward(
        self,
        hidden_states,
        attention_mask=None,
        head_mask=None,
        encoder_hidden_states=None,
        encoder_attention_mask=None,
        past_key_values=None,
        use_cache=None,
        output_attentions=False,
        output_hidden_states=False,
        return_dict=True,
        character_level_matrix=None,
        word_level_matrix=None,
    ):
        all_hidden_states = () if output_hidden_states else None
        all_self_attentions = () if output_attentions else None
        all_cross_attentions = () if output_attentions and self.config.add_cross_attention else None

        next_decoder_cache = () if use_cache else None

        for i, layer_module in enumerate(self.layer):
            if output_hidden_states:
                all_hidden_states = all_hidden_states + (hidden_states,)

            layer_head_mask = head_mask[i] if head_mask is not None else None
            past_key_value = past_key_values[i] if past_key_values is not None else None

            if self.gradient_checkpointing and self.training:

                if use_cache:
                    logger.warning(
                        "`use_cache=True` is incompatible with gradient checkpointing. Setting `use_cache=False`..."
                    )
                    use_cache = False

                def create_custom_forward(module):
                    def custom_forward(*inputs):
                        return module(*inputs, past_key_value, output_attentions)

                    return custom_forward

                if i < self.linguistic_information_selfattention_layer_num:
                    layer_outputs = torch.utils.checkpoint.checkpoint(
                        create_custom_forward(layer_module),
                        hidden_states,
                        attention_mask,
                        layer_head_mask,
                        encoder_hidden_states,
                        encoder_attention_mask,
                        character_level_matrix=character_level_matrix,
                        word_level_matrix=word_level_matrix,
                    )
                else:
                    layer_outputs = torch.utils.checkpoint.checkpoint(
                        create_custom_forward(layer_module),
                        hidden_states,
                        attention_mask,
                        layer_head_mask,
                        encoder_hidden_states,
                        encoder_attention_mask,
                    )
            else:
                if self.add_begin_attention_layer <= i < self.linguistic_information_selfattention_layer_num + self.add_begin_attention_layer:
                    layer_outputs = layer_module(
                        hidden_states,
                        attention_mask,
                        layer_head_mask,
                        encoder_hidden_states,
                        encoder_attention_mask,
                        past_key_value,
                        output_attentions,
                        character_level_matrix=character_level_matrix,
                        word_level_matrix=word_level_matrix,
                    )
                else:
                    layer_outputs = layer_module(
                        hidden_states,
                        attention_mask,
                        layer_head_mask,
                        encoder_hidden_states,
                        encoder_attention_mask,
                        past_key_value,
                        output_attentions,
                    )

            hidden_states = layer_outputs[0]
            if use_cache:
                next_decoder_cache += (layer_outputs[-1],)
            if output_attentions:
                all_self_attentions = all_self_attentions + (layer_outputs[1],)
                if self.config.add_cross_attention:
                    all_cross_attentions = all_cross_attentions + (layer_outputs[2],)

        if output_hidden_states:
            all_hidden_states = all_hidden_states + (hidden_states,)

        if not return_dict:
            return tuple(
                v
                for v in [
                    hidden_states,
                    next_decoder_cache,
                    all_hidden_states,
                    all_self_attentions,
                    all_cross_attentions,
                ]
                if v is not None
            )
        return BaseModelOutputWithPastAndCrossAttentions(
            last_hidden_state=hidden_states,
            past_key_values=next_decoder_cache,
            hidden_states=all_hidden_states,
            attentions=all_self_attentions,
            cross_attentions=all_cross_attentions,
        )


class BertPooler(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.activation = nn.Tanh()

    def forward(self, hidden_states):
        first_token_tensor = hidden_states[:, 0]
        pooled_output = self.dense(first_token_tensor)
        pooled_output = self.activation(pooled_output)
        return pooled_output


class BertModel(BertPreTrainedModel):
    def __init__(self, config, add_pooling_layer=True):
        super().__init__(config)
        self.config = config

        if self.config.with_linguistic_information_embedding_layer == "False":
            print("---Using BertEmbeddings---")
            self.embeddings = BertEmbeddings(config)
        else:
            print("---Using BertEmbeddings_ling---")
            self.embeddings = BertEmbeddings_ling(config)

        self.encoder = BertEncoder(config)
        self.pooler = BertPooler(config) if add_pooling_layer else None

    def get_input_embeddings(self):
        return self.embeddings.word_embeddings

    def set_input_embeddings(self, value):
        self.embeddings.word_embeddings = value

    def _prune_heads(self, heads_to_prune):
        for layer, heads in heads_to_prune.items():
            self.encoder.layer[layer].attention.prune_heads(heads)

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        position_ids=None,
        head_mask=None,
        inputs_embeds=None,
        encoder_hidden_states=None,
        encoder_attention_mask=None,
        past_key_values=None,
        use_cache=None,
        output_attentions=None,
        output_hidden_states=None,
        return_dict=None,
        character_level_ids=None,
        word_level_ids=None,
        character_level_matrix=None,
        word_level_matrix=None,
    ):
        output_attentions = output_attentions if output_attentions is not None else self.config.output_attentions
        output_hidden_states = (
            output_hidden_states if output_hidden_states is not None else self.config.output_hidden_states
        )
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        if self.config.is_decoder:
            use_cache = use_cache if use_cache is not None else self.config.use_cache
        else:
            use_cache = False

        if input_ids is not None and inputs_embeds is not None:
            raise ValueError("You cannot specify both input_ids and inputs_embeds at the same time")
        elif input_ids is not None:
            input_shape = input_ids.size()
        elif inputs_embeds is not None:
            input_shape = inputs_embeds.size()[:-1]
        else:
            raise ValueError("You have to specify either input_ids or inputs_embeds")

        batch_size, seq_length = input_shape
        device = input_ids.device if input_ids is not None else inputs_embeds.device

        past_key_values_length = past_key_values[0][0].shape[2] if past_key_values is not None else 0

        if attention_mask is None:
            attention_mask = torch.ones(((batch_size, seq_length + past_key_values_length)), device=device)

        if token_type_ids is None:
            if hasattr(self.embeddings, "token_type_ids"):
                buffered_token_type_ids = self.embeddings.token_type_ids[:, :seq_length]
                buffered_token_type_ids_expanded = buffered_token_type_ids.expand(batch_size, seq_length)
                token_type_ids = buffered_token_type_ids_expanded
            else:
                token_type_ids = torch.zeros(input_shape, dtype=torch.long, device=device)

        extended_attention_mask: torch.Tensor = self.get_extended_attention_mask(attention_mask, input_shape, device)

        if self.config.is_decoder and encoder_hidden_states is not None:
            encoder_batch_size, encoder_sequence_length, _ = encoder_hidden_states.size()
            encoder_hidden_shape = (encoder_batch_size, encoder_sequence_length)
            if encoder_attention_mask is None:
                encoder_attention_mask = torch.ones(encoder_hidden_shape, device=device)
            encoder_extended_attention_mask = self.invert_attention_mask(encoder_attention_mask)
        else:
            encoder_extended_attention_mask = None

        head_mask = self.get_head_mask(head_mask, self.config.num_hidden_layers)

        embedding_output = self.embeddings(
            input_ids=input_ids,
            position_ids=position_ids,
            token_type_ids=token_type_ids,
            inputs_embeds=inputs_embeds,
            past_key_values_length=past_key_values_length,
            character_level_ids=character_level_ids,
            word_level_ids=word_level_ids,
        )
        encoder_outputs = self.encoder(
            embedding_output,
            attention_mask=extended_attention_mask,
            head_mask=head_mask,
            encoder_hidden_states=encoder_hidden_states,
            encoder_attention_mask=encoder_extended_attention_mask,
            past_key_values=past_key_values,
            use_cache=use_cache,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
            character_level_matrix=character_level_matrix,
            word_level_matrix=word_level_matrix,
        )
        sequence_output = encoder_outputs[0]
        pooled_output = self.pooler(sequence_output) if self.pooler is not None else None

        if not return_dict:
            return (sequence_output, pooled_output) + encoder_outputs[1:]

        return BaseModelOutputWithPoolingAndCrossAttentions(
            last_hidden_state=sequence_output,
            pooler_output=pooled_output,
            past_key_values=encoder_outputs.past_key_values,
            hidden_states=encoder_outputs.hidden_states,
            attentions=encoder_outputs.attentions,
            cross_attentions=encoder_outputs.cross_attentions,
        )
