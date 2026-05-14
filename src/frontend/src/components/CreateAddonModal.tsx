import React, { useState } from 'react'
import { XCircle, ChevronRight, ChevronDown, FileText, Users, Settings2, MessageSquare } from 'lucide-react'
import * as api from '../api'
import {
  DEFAULT_MAX_REFINEMENTS,
  DEFAULT_EVOLVE_ITERATIONS,
  DEFAULT_NUM_PARENTS,
  DEFAULT_MAX_STREAMLINE_PROB,
  DEFAULT_WRITE_DIFFERENT_PROB,
  DEFAULT_NUM_EXTRA_SCORES
} from '../constants'

interface CreateAddonModalProps {
  task: api.Task;
  availableLiteratureIds: string[];
  onClose: () => void;
  onCreated: (task: api.Task) => void;
  isBackendDown: boolean;
}

const ADDON_DESCRIPTIONS: Record<string, string> = {
  'edit-theory': "Apply a custom modification to a theory",
  'evolve-loop': "Perform a Darwinian evolution on a population of theories, iteratively sampling parents, mutating them (via streamlining or refinement), and rescoring the results.",
  'expand-theory': "Expand a theory by applying suggested expansion reviews",
  'falsify-hypothesis': "Attempt to falsify a given hypothesis",
  'polish-theory': "Polish a theory to improve its clarity and make it easier to read. Does not add or remove any content, just rewords and restructures it.",
  'refine-hypothesis': "Attempt to refine a given hypothesis",
  'refine-theory': "Refine a theory by sequentially applying all its available reviews. Then applies a final polish step.",
  'refinement-loop': "Repeatedly review & refine a theory until no more major changes are needed.",
  'review-theory': "Perform a full review. Combines reviewing all statements in a theory and suggesting expansions into a single step.",
  'streamline-theory': "Streamline a theory down to its core essence.",
  'streamline-theory-variations': "Derive several different variations of a theory, each one focused on a different key aspect.",
  'suggest-expansions': "Suggest ways in which a theory can be expanded and/or generalized.",
  'score-theories': "Score the quality of the given theories relative to each other and update all population scores.",
  'write-different-theory': "Write a theory that explores a different approach from the provided theories."
};

type InputCategory = 'population' | 'theory' | 'statement';

const getAvailableSkills = (cat: InputCategory, reviewed: boolean): { id: string, label: string }[] => {
  if (cat === 'population') {
    return reviewed ? [
      { id: 'evolve-loop', label: 'Evolve Theory Loop' },
      { id: 'score-theories', label: 'Score Theories' },
      { id: 'write-different-theory', label: 'Write Different Theory' }
    ] : [
      { id: 'write-different-theory', label: 'Write Different Theory' }
    ];
  }
  if (cat === 'theory') {
    return reviewed ? [
      { id: 'edit-theory', label: 'Edit Theory' },
      { id: 'expand-theory', label: 'Expand Theory' },
      { id: 'polish-theory', label: 'Polish Theory' },
      { id: 'refine-theory', label: 'Refine Theory' },
      { id: 'refinement-loop', label: 'Refinement Loop' },
      { id: 'streamline-theory', label: 'Streamline Theory' },
      { id: 'streamline-theory-variations', label: 'Streamline Theory Variations' }
    ] : [
      { id: 'edit-theory', label: 'Edit Theory' },
      { id: 'polish-theory', label: 'Polish Theory' },
      { id: 'refinement-loop', label: 'Refinement Loop' },
      { id: 'review-theory', label: 'Review Theory' },
      { id: 'streamline-theory', label: 'Streamline Theory' },
      { id: 'streamline-theory-variations', label: 'Streamline Theory Variations' },
      { id: 'suggest-expansions', label: 'Suggest Expansions' }
    ];
  }
  if (cat === 'statement') {
    return reviewed ? [
      { id: 'refine-hypothesis', label: 'Refine Hypothesis' }
    ] : [
      { id: 'falsify-hypothesis', label: 'Falsify Hypothesis' }
    ];
  }
  return [];
};

export function CreateAddonModal({ task, availableLiteratureIds, onClose, onCreated, isBackendDown }: CreateAddonModalProps) {
  const [availableTheories, setAvailableTheories] = useState<api.TheoryArtifact[]>([])
  const [availableReviews, setAvailableReviews] = useState<api.ReviewArtifact[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const [inputCategory, setInputCategory] = useState<InputCategory>('theory')
  const [isReviewed, setIsReviewed] = useState(false)

  const sortedAndFilteredTheories = React.useMemo(() => {
    let theories = [...availableTheories].sort((a, b) => {
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
    if (isReviewed) {
      theories = theories.filter(t => availableReviews.some(r => r.parent_theory === t.id));
    }
    return theories;
  }, [availableTheories, availableReviews, isReviewed]);

  const initialSkills = getAvailableSkills('theory', false)
  const [addonType, setAddonType] = useState(initialSkills.length > 0 ? initialSkills[0].id : '')

  const [theoryId, setTheoryId] = useState('')
  const [theoryIds, setTheoryIds] = useState<string[]>([])

  React.useEffect(() => {
    setIsLoading(true)
    Promise.all([
      api.getTheories(task.id),
      api.getReviews(task.id)
    ])
      .then(([theories, reviews]) => {
        setAvailableTheories(theories)
        setAvailableReviews(reviews)
      })
      .catch(console.error)
      .finally(() => setIsLoading(false))
  }, [task.id])

  React.useEffect(() => {
    if (sortedAndFilteredTheories.length > 0 && !sortedAndFilteredTheories.find(t => t.id === theoryId)) {
      setTheoryId(sortedAndFilteredTheories[0].id)
    } else if (sortedAndFilteredTheories.length === 0) {
      setTheoryId('')
    }
  }, [sortedAndFilteredTheories, theoryId])

  const [direction, setDirection] = useState('')
  const [maxRefinements, setMaxRefinements] = useState(DEFAULT_MAX_REFINEMENTS)
  const [applyExpansions, setApplyExpansions] = useState('')
  const [evolveIterations, setEvolveIterations] = useState(DEFAULT_EVOLVE_ITERATIONS)
  const [numParents, setNumParents] = useState(DEFAULT_NUM_PARENTS)
  const [maxStreamlineProb, setMaxStreamlineProb] = useState(DEFAULT_MAX_STREAMLINE_PROB)
  const [writeDifferentProb, setWriteDifferentProb] = useState(DEFAULT_WRITE_DIFFERENT_PROB)
  const [numExtraScores, setNumExtraScores] = useState(DEFAULT_NUM_EXTRA_SCORES)

  const filteredReviews = availableReviews.filter(r => r.parent_theory === theoryId)
  const [reviewId, setReviewId] = useState(filteredReviews[0]?.id || '')

  // Update reviewId if filteredReviews changes and doesn't contain current reviewId
  React.useEffect(() => {
    if (filteredReviews.length > 0 && !filteredReviews.find(r => r.id === reviewId)) {
      setReviewId(filteredReviews[0].id)
    } else if (filteredReviews.length === 0) {
      setReviewId('')
    }
  }, [filteredReviews, reviewId])

  const [hypothesisTitle, setHypothesisTitle] = useState('')
  const [instruction, setInstruction] = useState('')
  const [litReviewId, setLitReviewId] = useState(availableLiteratureIds[0] || '')
  const [showAdditional, setShowAdditional] = useState(false)

  const hasRequiredConfig = ['falsify-hypothesis', 'edit-theory'].includes(addonType);
  const hasOptionalConfig = addonType === 'streamline-theory' ||
    ['refinement-loop', 'evolve-loop', 'refine-theory'].includes(addonType) ||
    (['edit-theory', 'expand-theory', 'refine-hypothesis', 'refine-theory', 'refinement-loop', 'evolve-loop', 'write-different-theory'].includes(addonType) && availableLiteratureIds.length > 0);

  const handleCategoryChange = (cat: InputCategory) => {
    setInputCategory(cat);
    const skills = getAvailableSkills(cat, isReviewed);
    setAddonType(skills.length > 0 ? skills[0].id : '');
  };

  const handleReviewedChange = (reviewed: boolean) => {
    setIsReviewed(reviewed);
    const skills = getAvailableSkills(inputCategory, reviewed);
    setAddonType(skills.length > 0 ? skills[0].id : '');
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const updatedTask = await api.createAddon(task.id, {
        type: addonType,
        theory_id: (inputCategory === 'population' || addonType === 'score-theories' || addonType === 'write-different-theory') ? undefined : theoryId,
        theory_ids: (addonType === 'score-theories' || addonType === 'write-different-theory') ? theoryIds : undefined,
        direction: addonType === 'streamline-theory' && direction ? direction : undefined,
        max_refinements: addonType === 'refinement-loop' ? maxRefinements : undefined,
        apply_expansions: (addonType === 'refinement-loop' || addonType === 'evolve-loop' || addonType === 'refine-theory') ? (applyExpansions || undefined) : undefined,
        evolve_iterations: addonType === 'evolve-loop' ? evolveIterations : undefined,
        num_parents: addonType === 'evolve-loop' ? numParents : undefined,
        max_streamline_prob: addonType === 'evolve-loop' ? maxStreamlineProb : undefined,
        write_different_prob: addonType === 'evolve-loop' ? writeDifferentProb : undefined,
        num_extra_scores: addonType === 'evolve-loop' ? numExtraScores : undefined,
        review_id: (addonType === 'refine-hypothesis' || addonType === 'expand-theory') ? reviewId : undefined,
        hypothesis_title: addonType === 'falsify-hypothesis' ? hypothesisTitle : undefined,
        instruction: addonType === 'edit-theory' ? instruction : undefined,
        lit_review_id: (['edit-theory', 'expand-theory', 'refine-hypothesis', 'refine-theory', 'refinement-loop', 'evolve-loop', 'write-different-theory'].includes(addonType)) ? (litReviewId || undefined) : undefined
      })
      onCreated(updatedTask)
    } catch (e: any) {
      alert(e.message || "Failed to add addon workflow")
    }
  }

  const isPopulation = inputCategory === 'population';

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white border-2 border-black p-8 w-full max-w-6xl shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] flex flex-col h-[1200px] max-h-[90vh]">
        <div className="flex justify-between items-center mb-8 shrink-0">
          <h2 className="text-2xl font-black tracking-tighter">Add Step</h2>
          <button onClick={onClose} className="hover:rotate-90 transition-transform">
            <XCircle size={24} />
          </button>
        </div>

        <form onSubmit={handleCreate} className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto custom-scrollbar pr-4 flex flex-col gap-10 pb-4">

            {/* STEP 1: Input Type */}
            <div>
              <h3 className="text-sm font-black mb-4">Step 1: I have a...</h3>
              <div className="flex flex-col md:flex-row gap-4">
                <label
                  className={`flex-1 border-2 p-4 cursor-pointer transition-colors flex flex-col justify-center ${inputCategory === 'population' ? 'border-black bg-gray-50 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]' : 'border-gray-200 hover:border-gray-400'} ${availableTheories.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}`}
                  title={availableTheories.length === 0 ? "No theories have been generated yet in this task. Please wait for a step to generate a theory." : ""}
                >
                  <div className="flex items-center gap-3">
                    <input type="radio" checked={inputCategory === 'population'} onChange={() => handleCategoryChange('population')} disabled={availableTheories.length === 0} />
                    <Users size={18} className="text-gray-600" />
                    <span className="font-black text-sm">Population of Theories</span>
                  </div>
                </label>
                <label
                  className={`flex-1 border-2 p-4 cursor-pointer transition-colors flex flex-col justify-center ${inputCategory === 'theory' ? 'border-black bg-gray-50 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]' : 'border-gray-200 hover:border-gray-400'} ${availableTheories.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}`}
                  title={availableTheories.length === 0 ? "No theories have been generated yet in this task. Please wait for a step to generate a theory." : ""}
                >
                  <div className="flex items-center gap-3">
                    <input type="radio" checked={inputCategory === 'theory'} onChange={() => handleCategoryChange('theory')} disabled={availableTheories.length === 0} />
                    <FileText size={18} className="text-gray-600" />
                    <span className="font-black text-sm">Theory</span>
                  </div>
                </label>
                <label
                  className={`flex-1 border-2 p-4 cursor-pointer transition-colors flex flex-col justify-center ${inputCategory === 'statement' ? 'border-black bg-gray-50 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]' : 'border-gray-200 hover:border-gray-400'} ${availableTheories.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}`}
                  title={availableTheories.length === 0 ? "No theories have been generated yet in this task. Please wait for a step to generate a theory." : ""}
                >
                  <div className="flex items-center gap-3">
                    <input type="radio" checked={inputCategory === 'statement'} onChange={() => handleCategoryChange('statement')} disabled={availableTheories.length === 0} />
                    <MessageSquare size={18} className="text-gray-600" />
                    <span className="font-black text-sm">Statement Within a Theory</span>
                  </div>
                </label>
              </div>

              <div className="mt-4">
                <label
                  className={`flex items-center gap-3 cursor-pointer group w-fit ${(availableReviews.length === 0) ? 'opacity-50 cursor-not-allowed' : ''}`}
                  title={availableReviews.length === 0 ? "Requires at least one review." : ""}
                >
                  <div className="relative flex items-center justify-center w-5 h-5 border-2 border-black group-hover:border-gray-500 transition-colors">
                    <input
                      type="checkbox"
                      className="absolute opacity-0 w-full h-full cursor-pointer"
                      checked={isReviewed}
                      onChange={e => handleReviewedChange(e.target.checked)}
                      disabled={availableReviews.length === 0}
                    />
                    {isReviewed && <div className="w-3 h-3 bg-black" />}
                  </div>
                  <span className="text-sm font-bold">...which has already been reviewed</span>
                </label>
              </div>
            </div>

            {/* STEP 2: Action */}
            <div>
              <h3 className="text-sm font-black mb-4">
                Step 2: And I want to...
              </h3>
              {getAvailableSkills(inputCategory, isReviewed).length === 0 ? (
                <div className="text-sm font-bold text-gray-500 italic p-4 border-2 border-dashed border-gray-200">
                  No skills available for this context. Please ensure you have generated theories or reviews as required, or check the 'already reviewed' option if applicable.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {getAvailableSkills(inputCategory, isReviewed).map(skill => (
                    <label key={skill.id} className={`border-2 p-4 cursor-pointer transition-colors flex flex-col gap-2 ${addonType === skill.id ? 'border-black bg-gray-50 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]' : 'border-gray-200 hover:border-gray-400'}`}>
                      <div className="flex items-start gap-3">
                        <input type="radio" name="addonSkill" className="mt-1" checked={addonType === skill.id} onChange={() => setAddonType(skill.id)} />
                        <div>
                          <span className="font-black text-sm">{skill.label}</span>
                          <p className="text-[10px] text-gray-500 font-bold leading-relaxed mt-2">
                            {ADDON_DESCRIPTIONS[skill.id]}
                          </p>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* STEP 3: Targets */}
            {(!isPopulation || addonType === 'score-theories' || addonType === 'write-different-theory') && (
              <div>
                <h3 className="text-sm font-black mb-4">Step 3: Select Targets</h3>
                <div className="flex flex-col gap-6">
                  <div>
                    <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">
                      {(addonType === 'score-theories' || addonType === 'write-different-theory') ? 'Target Theories' : 'Target Theory'}
                    </label>
                    {(addonType === 'score-theories' || addonType === 'write-different-theory') ? (
                      <select
                        multiple
                        required
                        value={theoryIds}
                        onChange={e => setTheoryIds(Array.from(e.target.selectedOptions, option => option.value))}
                        className="w-full border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed h-48"
                        disabled={isLoading || sortedAndFilteredTheories.length === 0}
                      >
                        {isLoading ? (
                          <option value="">Loading...</option>
                        ) : sortedAndFilteredTheories.length === 0 ? (
                          <option value="">No theories found</option>
                        ) : (
                          sortedAndFilteredTheories.map(t => (
                            <option key={t.id} value={t.id}>{t.headline ? `${t.id}: ${t.headline}` : t.id}</option>
                          ))
                        )}
                      </select>
                    ) : (
                      <select
                        required
                        value={theoryId}
                        onChange={e => setTheoryId(e.target.value)}
                        className="w-full border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={isLoading || sortedAndFilteredTheories.length === 0}
                      >
                        {isLoading ? (
                          <option value="">Loading...</option>
                        ) : sortedAndFilteredTheories.length === 0 ? (
                          <option value="">No theories found</option>
                        ) : (
                          sortedAndFilteredTheories.map(t => (
                            <option key={t.id} value={t.id}>{t.headline ? `${t.id}: ${t.headline}` : t.id}</option>
                          ))
                        )}
                      </select>
                    )}
                  </div>

                  {(addonType === 'refine-hypothesis' || addonType === 'expand-theory') && (
                    <div>
                      <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Apply Review</label>
                      {isLoading ? (
                        <select
                          disabled
                          className="w-full border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-not-allowed opacity-50"
                        >
                          <option value="">Loading...</option>
                        </select>
                      ) : filteredReviews.length > 0 ? (
                        <select
                          required
                          value={reviewId}
                          onChange={e => setReviewId(e.target.value)}
                          className="w-full border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-pointer"
                        >
                          {filteredReviews.map(r => (
                            <option key={r.id} value={r.id}>{r.headline ? `${r.id}: ${r.headline}` : r.id}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          required
                          value={reviewId}
                          onChange={e => setReviewId(e.target.value)}
                          placeholder="R_YYYYMMDD_..."
                          className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200"
                        />
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* STEP 4: Configuration */}
            {(hasRequiredConfig || hasOptionalConfig) && (
              <div>
                <h3 className="text-sm font-black mb-4">
                  {isPopulation ? 'Step 3: Configuration' : 'Step 4: Configuration'}
                </h3>
                <div className="flex flex-col gap-6">

                  {/* Required Configurations */}
                  {addonType === 'falsify-hypothesis' && (
                    <div>
                      <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Hypothesis Title</label>
                      <input
                        type="text"
                        required
                        value={hypothesisTitle}
                        onChange={e => setHypothesisTitle(e.target.value)}
                        placeholder="Enter the title of the hypothesis to review"
                        className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200"
                      />
                    </div>
                  )}

                  {addonType === 'edit-theory' && (
                    <div>
                      <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Edit Instructions</label>
                      <textarea
                        required
                        rows={5}
                        value={instruction}
                        onChange={e => setInstruction(e.target.value)}
                        placeholder="Describe the edits you want to make to the theory..."
                        className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200 resize-none"
                      />
                    </div>
                  )}

                  {/* Optional Configurations */}
                  {hasOptionalConfig && (
                    <div className="space-y-6">
                      <button
                        type="button"
                        onClick={() => setShowAdditional(!showAdditional)}
                        className="flex items-center gap-2 text-[10px] font-black tracking-widest hover:text-gray-500 transition-colors group"
                      >
                        <Settings2 size={14} />
                        <span>Additional Parameters</span>
                        {showAdditional ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </button>

                      {showAdditional && (
                        <div className="flex flex-col gap-6 p-6 border-2 border-dashed border-gray-200">
                          {addonType === 'refinement-loop' && (
                            <div>
                              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Refinement Iterations</label>
                              <input
                                type="number"
                                min="1"
                                max="10"
                                required
                                value={maxRefinements}
                                onChange={e => setMaxRefinements(parseInt(e.target.value, 10))}
                                className="w-full md:w-1/3 border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                              />
                            </div>
                          )}

                          {addonType === 'evolve-loop' && (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                              <div>
                                <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Iterations</label>
                                <input
                                  type="number" min="1" max="10" required
                                  value={evolveIterations} onChange={e => setEvolveIterations(parseInt(e.target.value, 10))}
                                  className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                                />
                              </div>
                              <div>
                                <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Num Parents</label>
                                <input
                                  type="number" min="1" max="10" required
                                  value={numParents} onChange={e => setNumParents(parseInt(e.target.value, 10))}
                                  className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                                />
                              </div>
                              <div>
                                <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Max Streamline Prob</label>
                                <input
                                  type="number" min="0" max="1" step="any" required
                                  value={maxStreamlineProb} onChange={e => setMaxStreamlineProb(parseFloat(e.target.value))}
                                  className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                                />
                              </div>
                              <div>
                                <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Write Different Prob</label>
                                <input
                                  type="number" min="0" max="1" step="any" required
                                  value={writeDifferentProb} onChange={e => setWriteDifferentProb(parseFloat(e.target.value))}
                                  className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                                />
                              </div>
                              <div>
                                <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Extra Scores</label>
                                <input
                                  type="number" min="0" max="10" required
                                  value={numExtraScores} onChange={e => setNumExtraScores(parseInt(e.target.value, 10))}
                                  className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold"
                                />
                              </div>
                            </div>
                          )}

                          {addonType === 'streamline-theory' && (
                            <div>
                              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Streamlining Direction (Optional)</label>
                              <input
                                type="text"
                                value={direction}
                                onChange={e => setDirection(e.target.value)}
                                placeholder="e.g., focus on aspect XY"
                                className="w-full border-2 border-black p-3 outline-none focus:bg-gray-50 text-sm font-bold placeholder:text-gray-200"
                              />
                            </div>
                          )}

                          {['edit-theory', 'expand-theory', 'refine-hypothesis', 'refine-theory', 'refinement-loop', 'evolve-loop', 'write-different-theory'].includes(addonType) && availableLiteratureIds.length > 0 && (
                            <div>
                              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Literature Review ID (Optional)</label>
                              <select
                                value={litReviewId}
                                onChange={e => setLitReviewId(e.target.value)}
                                className="w-full md:w-1/2 border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-pointer"
                              >
                                <option value="">None (Optional)</option>
                                {availableLiteratureIds.map(id => (
                                  <option key={id} value={id}>{id}</option>
                                ))}
                              </select>
                            </div>
                          )}

                          {(addonType === 'refinement-loop' || addonType === 'evolve-loop' || addonType === 'refine-theory') && (
                            <div>
                              <label className="block text-[10px] font-black mb-2 tracking-widest text-gray-400">Apply Expansion Reviews</label>
                              <select
                                value={applyExpansions}
                                onChange={e => setApplyExpansions(e.target.value)}
                                className="w-full md:w-1/3 border-2 border-black p-3 outline-none font-bold text-sm bg-white cursor-pointer"
                              >
                                <option value="">Auto (Default)</option>
                                <option value="always">Always</option>
                                <option value="never">Never</option>
                              </select>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                </div>
              </div>
            )}
          </div>

          <div className="flex gap-4 pt-6 border-t border-gray-100 shrink-0 mt-4">
            <button
              type="submit"
              disabled={isBackendDown || !addonType || (!isPopulation && addonType !== 'score-theories' && !theoryId) || (addonType === 'score-theories' && theoryIds.length === 0)}
              className="flex-1 bg-black text-white p-4 font-black text-sm tracking-widest hover:bg-gray-800 transition-all flex items-center justify-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
            >
              {isBackendDown ? 'Backend Offline' : 'Add Step'} <ChevronRight size={18} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
